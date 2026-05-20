"""
Wiring del firmware: une bus + hardware + dispensador y arranca tareas de fondo.

Tareas de fondo:
- Heartbeat: publica estado de la máquina cada N segundos.
- LeakWatcher: monitorea pulsos cuando la máquina está IDLE; si detecta flujo
  no autorizado emite LeakDetected.
"""
from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass

from loguru import logger
from pydantic import BaseModel

from edge_water import __version__
from edge_water.bus import Bus, InMemoryBus
from edge_water.bus.mqtt import MqttBus
from edge_water.config import Settings
from edge_water.dispenser import Dispenser
from edge_water.hardware.base import FlowMeter, LedColor, Pump, StatusLed, Valve
from edge_water.hardware.mock import MockFlowMeter, MockLed, MockPump, MockValve
from edge_water.messages import (
    CMD_ABORT,
    CMD_DISPENSE,
    EVT_DISPENSE_COMPLETED,
    EVT_DISPENSE_FAILED,
    EVT_DISPENSE_PROGRESS,
    EVT_DISPENSE_STARTED,
    EVT_HEARTBEAT,
    EVT_LEAK,
    EVT_TELEMETRY,
    AbortCommand,
    DispenseCommand,
    DispenseCompleted,
    DispenseFailed,
    DispenseProgress,
    DispenseStarted,
    Heartbeat,
    LeakDetected,
    Telemetry,
)


_EVENT_TOPICS: dict[type[BaseModel], str] = {
    DispenseStarted: EVT_DISPENSE_STARTED,
    DispenseProgress: EVT_DISPENSE_PROGRESS,
    DispenseCompleted: EVT_DISPENSE_COMPLETED,
    DispenseFailed: EVT_DISPENSE_FAILED,
    Heartbeat: EVT_HEARTBEAT,
    LeakDetected: EVT_LEAK,
    Telemetry: EVT_TELEMETRY,
}


@dataclass
class HardwareSet:
    valve: Valve
    pump: Pump
    flow_meter: FlowMeter
    led: StatusLed


def build_mock_hardware() -> HardwareSet:
    valve = MockValve()
    pump = MockPump()
    flow = MockFlowMeter(valve, pump)
    led = MockLed()
    return HardwareSet(valve=valve, pump=pump, flow_meter=flow, led=led)


def build_real_hardware(settings: Settings) -> HardwareSet:
    # Import diferido: solo se ejecuta en la Pi.
    from edge_water.hardware.real import RealFlowMeter, RealLed, RealPump, RealValve

    valve = RealValve(settings.gpio_valve, active_low=settings.relay_active_low)
    pump = RealPump(settings.gpio_pump, active_low=settings.relay_active_low)
    flow = RealFlowMeter(settings.gpio_flow_meter)
    led = RealLed(settings.gpio_led)
    return HardwareSet(valve=valve, pump=pump, flow_meter=flow, led=led)


def build_bus(settings: Settings, *, in_memory: InMemoryBus | None = None) -> Bus:
    if settings.bus_mode == "memory":
        return in_memory or InMemoryBus()
    return MqttBus(
        host=settings.mqtt_host,
        port=settings.mqtt_port,
        username=settings.mqtt_username,
        password=settings.mqtt_password,
        tls=settings.mqtt_tls,
        client_id=f"edge-{settings.machine_id}",
    )


class App:
    """Aplicación completa: bus + hardware + dispensador + tareas de fondo."""

    def __init__(
        self,
        settings: Settings,
        hardware: HardwareSet,
        bus: Bus,
    ) -> None:
        self._settings = settings
        self._hw = hardware
        self._bus = bus
        self._started_at = 0.0
        self._tasks: list[asyncio.Task[None]] = []

        self._dispenser = Dispenser(
            machine_id=settings.machine_id,
            valve=hardware.valve,
            pump=hardware.pump,
            flow_meter=hardware.flow_meter,
            led=hardware.led,
            emit=self._publish_event,
            pulses_per_liter=settings.pulses_per_liter,
            default_timeout_s=settings.dispense_timeout_s,
            no_flow_timeout_s=settings.no_flow_timeout_s,
            progress_interval_ms=settings.progress_interval_ms,
        )

    @property
    def dispenser(self) -> Dispenser:
        return self._dispenser

    async def _publish_event(self, event: BaseModel) -> None:
        topic_suffix = _EVENT_TOPICS.get(type(event))
        if topic_suffix is None:
            logger.warning("Evento sin topic registrado: {}", type(event).__name__)
            return
        topic = f"{self._settings.topic_prefix}/{topic_suffix}"
        payload = event.model_dump_json().encode("utf-8")
        await self._bus.publish(topic, payload)

    async def _on_dispense_cmd(self, _topic: str, payload: bytes) -> None:
        try:
            cmd = DispenseCommand.model_validate_json(payload)
        except Exception:  # noqa: BLE001
            logger.exception("Payload inválido en cmd/dispense")
            return
        await self._dispenser.handle_dispense(cmd)

    async def _on_abort_cmd(self, _topic: str, payload: bytes) -> None:
        try:
            cmd = AbortCommand.model_validate_json(payload)
        except Exception:  # noqa: BLE001
            logger.exception("Payload inválido en cmd/abort")
            return
        await self._dispenser.handle_abort(cmd)

    async def start(self) -> None:
        await self._bus.start()
        prefix = self._settings.topic_prefix
        await self._bus.subscribe(f"{prefix}/{CMD_DISPENSE}", self._on_dispense_cmd)
        await self._bus.subscribe(f"{prefix}/{CMD_ABORT}", self._on_abort_cmd)
        self._started_at = time.monotonic()
        self._tasks.append(asyncio.create_task(self._heartbeat_loop(), name="heartbeat"))
        self._tasks.append(asyncio.create_task(self._leak_watcher(), name="leak-watcher"))
        logger.info(
            "Edge {} listo. hardware={} bus={}",
            self._settings.machine_id,
            self._settings.hardware_mode,
            self._settings.bus_mode,
        )

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        await self._bus.stop()
        try:
            self._hw.valve.close()
            self._hw.pump.stop()
            self._hw.led.set(LedColor.off)
        except Exception:  # noqa: BLE001
            logger.exception("Error en cleanup de hardware")

    async def _heartbeat_loop(self) -> None:
        interval = self._settings.heartbeat_interval_s
        while True:
            try:
                await self._publish_event(
                    Heartbeat(
                        machine_id=self._settings.machine_id,
                        uptime_s=time.monotonic() - self._started_at,
                        firmware_version=__version__,
                        state=self._dispenser.state,
                    )
                )
            except Exception:  # noqa: BLE001
                logger.exception("Heartbeat falló")
            await asyncio.sleep(interval)

    async def _leak_watcher(self) -> None:
        """Si en estado idle el caudalímetro registra pulsos significativos,
        algo está fluyendo sin autorización (válvula fallando, manipulación)."""
        last = self._hw.flow_meter.total_pulses
        threshold_pulses = max(5, int(self._settings.pulses_per_liter * 0.01))  # ~10ml
        while True:
            await asyncio.sleep(2.0)
            current = self._hw.flow_meter.total_pulses
            if self._dispenser.state == "idle":
                delta = current - last
                if delta >= threshold_pulses:
                    liters = delta / self._settings.pulses_per_liter
                    logger.warning("Posible fuga: {} pulsos en idle", delta)
                    await self._publish_event(
                        LeakDetected(
                            machine_id=self._settings.machine_id,
                            pulses=delta,
                            liters_estimated=liters,
                        )
                    )
                    self._hw.led.set(LedColor.leak)
            last = current


@asynccontextmanager
async def run_app(settings: Settings):
    if settings.hardware_mode == "real":
        hw = build_real_hardware(settings)
    else:
        hw = build_mock_hardware()
    bus = build_bus(settings)
    app = App(settings, hw, bus)
    await app.start()
    try:
        yield app
    finally:
        await app.stop()


def event_topic(model_cls: type[BaseModel]) -> str | None:
    return _EVENT_TOPICS.get(model_cls)


def encode_command(cmd: BaseModel) -> bytes:
    return cmd.model_dump_json().encode("utf-8")


def decode_event(topic: str, payload: bytes) -> BaseModel | None:
    """Decodifica un evento publicado por el edge según su topic."""
    suffix = topic.rsplit("/", 1)[-1]
    cls_by_suffix = {
        "dispense_started": DispenseStarted,
        "dispense_progress": DispenseProgress,
        "dispense_completed": DispenseCompleted,
        "dispense_failed": DispenseFailed,
        "heartbeat": Heartbeat,
        "leak_detected": LeakDetected,
        "telemetry": Telemetry,
    }
    cls = cls_by_suffix.get(suffix)
    if not cls:
        return None
    try:
        return cls.model_validate_json(payload)
    except Exception:  # noqa: BLE001
        return None


__all__ = [
    "App",
    "HardwareSet",
    "build_bus",
    "build_mock_hardware",
    "build_real_hardware",
    "decode_event",
    "encode_command",
    "event_topic",
    "run_app",
]
