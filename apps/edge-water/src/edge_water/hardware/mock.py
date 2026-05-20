"""
Hardware simulado en software. Modela:
- Una válvula y bomba con estado on/off.
- Un caudalímetro que SOLO emite pulsos cuando válvula+bomba están activas.
- Modos de falla configurables: stuck (sin pulsos), slow, leak (pulsos sin orden), partial_stop (corta a mitad).

El caudalímetro mock arranca un thread que incrementa el contador a una tasa
configurable (pulsos/segundo). Esto simula el comportamiento real donde los
pulsos llegan desde una ISR independiente.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from edge_water.hardware.base import LedColor


class MockValve:
    def __init__(self) -> None:
        self._open = False

    def open(self) -> None:
        self._open = True

    def close(self) -> None:
        self._open = False

    @property
    def is_open(self) -> bool:
        return self._open


class MockPump:
    def __init__(self) -> None:
        self._running = False

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running


@dataclass
class MockFlowMeterConfig:
    """Modos de falla para probar el firmware."""
    pulses_per_second: float = 75.0   # ~10 L/min con 450 pulsos/L
    stuck: bool = False               # No emite pulsos aunque haya válvula+bomba
    leak_rate: float = 0.0            # Pulsos/seg incluso con válvula cerrada
    stop_after_pulses: int | None = None  # Se detiene espontáneamente tras N pulsos


class MockFlowMeter:
    """Caudalímetro simulado. Necesita referencia a la válvula y bomba para
    decidir si está fluyendo agua."""

    def __init__(
        self,
        valve: MockValve,
        pump: MockPump,
        config: MockFlowMeterConfig | None = None,
    ) -> None:
        self._valve = valve
        self._pump = pump
        self._config = config or MockFlowMeterConfig()
        self._lock = threading.Lock()
        self._pulses = 0
        self._stop_evt = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="mock-flow")
        self._thread.start()

    def _run(self) -> None:
        last = time.monotonic()
        accum = 0.0
        leak_accum = 0.0
        while not self._stop_evt.is_set():
            time.sleep(0.01)
            now = time.monotonic()
            dt = now - last
            last = now

            cfg = self._config
            flowing = self._valve.is_open and self._pump.is_running and not cfg.stuck
            if flowing:
                accum += cfg.pulses_per_second * dt
                whole = int(accum)
                if whole > 0:
                    accum -= whole
                    with self._lock:
                        self._pulses += whole
                        if cfg.stop_after_pulses is not None and self._pulses >= cfg.stop_after_pulses:
                            # Simula que la bomba/válvula falla a mitad de camino.
                            self._config = MockFlowMeterConfig(stuck=True)
            elif cfg.leak_rate > 0:
                leak_accum += cfg.leak_rate * dt
                whole = int(leak_accum)
                if whole > 0:
                    leak_accum -= whole
                    with self._lock:
                        self._pulses += whole

    @property
    def total_pulses(self) -> int:
        with self._lock:
            return self._pulses

    def reset(self) -> None:
        with self._lock:
            self._pulses = 0

    def configure(self, config: MockFlowMeterConfig) -> None:
        """Cambia el comportamiento en caliente (útil para inyectar fallas durante un test)."""
        self._config = config

    def shutdown(self) -> None:
        self._stop_evt.set()
        self._thread.join(timeout=1.0)


@dataclass
class MockLed:
    color: LedColor = LedColor.off
    history: list[LedColor] = field(default_factory=list)

    def set(self, color: LedColor) -> None:
        self.color = color
        self.history.append(color)
