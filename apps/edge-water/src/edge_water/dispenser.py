"""
Lógica central del dispensado.

Responsabilidades:
- Mantener invariante: NUNCA dejar la válvula abierta o la bomba prendida si no
  hay una orden activa (cleanup en finally).
- Confirmar dispensado por sensor (caudalímetro), no por tiempo.
- Detectar atasco (sin pulsos por N seg), timeout total, abort externo, overflow.
- Idempotencia: una misma `order_id` no dispensa dos veces.
- Emitir eventos al exterior (DispenseStarted/Progress/Completed/Failed) vía callback,
  desacoplado del bus subyacente.
"""
from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Awaitable, Callable
from typing import Literal

from loguru import logger
from pydantic import BaseModel

from edge_water.hardware.base import FlowMeter, LedColor, Pump, StatusLed, Valve
from edge_water.messages import (
    AbortCommand,
    DispenseCommand,
    DispenseCompleted,
    DispenseFailed,
    DispenseProgress,
    DispenseStarted,
    FailureReason,
)

EventEmit = Callable[[BaseModel], Awaitable[None]]


# Tolerancia: si fluye más de target * (1+OVERFLOW_PCT) → fallo, válvula no cerró bien.
OVERFLOW_PCT = 0.05


class Dispenser:
    def __init__(
        self,
        *,
        machine_id: str,
        valve: Valve,
        pump: Pump,
        flow_meter: FlowMeter,
        led: StatusLed,
        emit: EventEmit,
        pulses_per_liter: float,
        default_timeout_s: float = 120.0,
        no_flow_timeout_s: float = 5.0,
        progress_interval_ms: int = 500,
    ) -> None:
        self._machine_id = machine_id
        self._valve = valve
        self._pump = pump
        self._flow = flow_meter
        self._led = led
        self._emit = emit

        self._pulses_per_liter = pulses_per_liter
        self._default_timeout_s = default_timeout_s
        self._no_flow_timeout_s = no_flow_timeout_s
        self._progress_interval_s = progress_interval_ms / 1000.0

        self._active_order: str | None = None
        self._abort_event = asyncio.Event()
        self._abort_reason: str | None = None
        self._processed: deque[str] = deque(maxlen=200)

        self._led.set(LedColor.idle)

    @property
    def state(self) -> Literal["idle", "dispensing"]:
        return "dispensing" if self._active_order else "idle"

    @property
    def active_order_id(self) -> str | None:
        return self._active_order

    async def handle_dispense(self, cmd: DispenseCommand) -> None:
        """Procesa un comando de dispensar. Es idempotente: una `order_id` ya
        vista (en curso o ya completada) se ignora silenciosamente."""
        if cmd.order_id in self._processed:
            logger.info("Orden {} ya procesada, ignorando (idempotencia)", cmd.order_id)
            return
        if self._active_order == cmd.order_id:
            logger.info("Orden {} ya en curso, ignorando", cmd.order_id)
            return

        # Si hay OTRA orden en curso, rechazamos (busy).
        if self._active_order is not None:
            await self._emit(
                DispenseFailed(
                    machine_id=self._machine_id,
                    order_id=cmd.order_id,
                    reason=FailureReason.busy,
                    liters_partial=0.0,
                    detail=f"Máquina ocupada con orden {self._active_order}",
                )
            )
            return

        # Reserva síncrona: cualquier comando concurrente verá active_order y será busy.
        self._active_order = cmd.order_id
        self._abort_event.clear()
        self._abort_reason = None
        await self._run_dispense(cmd)

    async def handle_abort(self, cmd: AbortCommand) -> None:
        if self._active_order != cmd.order_id:
            logger.info("Abort para orden {} ignorado (activa={})", cmd.order_id, self._active_order)
            return
        self._abort_reason = cmd.reason or "aborted"
        self._abort_event.set()
        logger.warning("Abort recibido para orden {}: {}", cmd.order_id, self._abort_reason)

    async def _run_dispense(self, cmd: DispenseCommand) -> None:
        order_id = cmd.order_id
        target_liters = cmd.liters
        target_pulses = int(round(target_liters * self._pulses_per_liter))
        timeout_s = cmd.timeout_s or self._default_timeout_s

        self._flow.reset()

        await self._emit(
            DispenseStarted(
                machine_id=self._machine_id,
                order_id=order_id,
                liters_target=target_liters,
            )
        )
        self._led.set(LedColor.dispensing)
        start = time.monotonic()
        last_pulse_count = 0
        last_pulse_change_t = start

        try:
            try:
                self._valve.open()
                self._pump.start()
            except Exception as e:  # noqa: BLE001
                logger.exception("Falló al activar hardware")
                await self._fail(order_id, FailureReason.hardware, 0.0, str(e))
                return

            while True:
                # Espera un tick o hasta que llegue un abort.
                try:
                    await asyncio.wait_for(self._abort_event.wait(), timeout=self._progress_interval_s)
                    # Si despertó es porque se pidió abort.
                    pulses = self._flow.total_pulses
                    await self._fail(
                        order_id,
                        FailureReason.aborted,
                        pulses / self._pulses_per_liter,
                        self._abort_reason,
                    )
                    return
                except TimeoutError:
                    pass  # tick normal

                pulses = self._flow.total_pulses
                liters = pulses / self._pulses_per_liter
                now = time.monotonic()

                if pulses != last_pulse_count:
                    last_pulse_count = pulses
                    last_pulse_change_t = now

                # Éxito
                if pulses >= target_pulses:
                    duration_ms = int((now - start) * 1000)
                    self._valve.close()
                    self._pump.stop()
                    await self._emit(
                        DispenseCompleted(
                            machine_id=self._machine_id,
                            order_id=order_id,
                            liters_target=target_liters,
                            liters_actual=liters,
                            duration_ms=duration_ms,
                        )
                    )
                    self._led.set(LedColor.success)
                    self._processed.append(order_id)
                    return

                # Timeout total
                if (now - start) >= timeout_s:
                    await self._fail(order_id, FailureReason.timeout, liters)
                    return

                # Atasco / sin agua
                if (now - last_pulse_change_t) >= self._no_flow_timeout_s:
                    await self._fail(order_id, FailureReason.no_flow, liters)
                    return

                # Overflow (válvula no cierra, sigue corriendo)
                if pulses > target_pulses * (1 + OVERFLOW_PCT):
                    await self._fail(order_id, FailureReason.overflow, liters)
                    return

                # Reporte de progreso
                percent = min(100.0, (pulses / target_pulses) * 100.0) if target_pulses else 0.0
                await self._emit(
                    DispenseProgress(
                        machine_id=self._machine_id,
                        order_id=order_id,
                        liters_so_far=liters,
                        pulses=pulses,
                        percent=percent,
                    )
                )
        finally:
            # Garantía de seguridad: cerrar todo SIEMPRE.
            try:
                self._valve.close()
            except Exception:  # noqa: BLE001
                logger.exception("Error cerrando válvula en cleanup")
            try:
                self._pump.stop()
            except Exception:  # noqa: BLE001
                logger.exception("Error parando bomba en cleanup")
            self._active_order = None
            # No bajamos el LED de success aquí; lo deja la siguiente transición a idle.

    async def _fail(
        self,
        order_id: str,
        reason: FailureReason,
        liters_partial: float,
        detail: str | None = None,
    ) -> None:
        # Importante: cerrar válvula/bomba ANTES de emitir el evento, para que el
        # estado físico ya sea seguro cuando el backend reaccione.
        try:
            self._valve.close()
            self._pump.stop()
        except Exception:  # noqa: BLE001
            logger.exception("Error apagando hardware en _fail")
        await self._emit(
            DispenseFailed(
                machine_id=self._machine_id,
                order_id=order_id,
                reason=reason,
                liters_partial=liters_partial,
                detail=detail,
            )
        )
        self._led.set(LedColor.error)
        self._processed.append(order_id)
