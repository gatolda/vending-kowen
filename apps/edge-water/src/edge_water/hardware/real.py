"""
Implementación real con gpiozero (sobre pigpio para precisión en el conteo de pulsos).

NO se importa en mock/desarrollo. La fábrica `build_real_hardware()` solo se llama
cuando HARDWARE_MODE=real, lo cual se detecta en `app.py`. Esto permite ejecutar
el firmware en Windows/macOS sin instalar gpiozero.

Setup en la Pi:
    sudo apt install pigpio python3-pigpio
    sudo systemctl enable --now pigpiod
    pip install -e ".[hardware]"
"""
from __future__ import annotations

import threading

# Estos imports SOLO funcionan en la Pi. Quedan dentro del módulo.
from gpiozero import DigitalOutputDevice, Button  # type: ignore[import-not-found]
from gpiozero.pins.pigpio import PiGPIOFactory  # type: ignore[import-not-found]

from edge_water.hardware.base import LedColor


_pin_factory = PiGPIOFactory()


class RealValve:
    """Válvula NC controlada por relé. `active_low=True` significa que el relé
    se activa con LOW (típico en placas chinas baratas)."""

    def __init__(self, gpio: int, active_low: bool = True) -> None:
        self._dev = DigitalOutputDevice(gpio, active_high=not active_low, pin_factory=_pin_factory)

    def open(self) -> None:
        self._dev.on()

    def close(self) -> None:
        self._dev.off()

    @property
    def is_open(self) -> bool:
        return bool(self._dev.value)


class RealPump:
    def __init__(self, gpio: int, active_low: bool = True) -> None:
        self._dev = DigitalOutputDevice(gpio, active_high=not active_low, pin_factory=_pin_factory)

    def start(self) -> None:
        self._dev.on()

    def stop(self) -> None:
        self._dev.off()

    @property
    def is_running(self) -> bool:
        return bool(self._dev.value)


class RealFlowMeter:
    """Caudalímetro YF-S201 conectado al GPIO. Cada flanco ascendente incrementa el contador.
    Thread-safe: las callbacks de gpiozero corren en un thread interno."""

    def __init__(self, gpio: int) -> None:
        self._lock = threading.Lock()
        self._pulses = 0
        # `Button` con pull_up=True es la forma idiomática en gpiozero de leer
        # un señal pulsada. El YF-S201 idle en HIGH y baja con cada vuelta.
        self._btn = Button(gpio, pull_up=True, pin_factory=_pin_factory, bounce_time=None)
        self._btn.when_pressed = self._on_pulse

    def _on_pulse(self) -> None:
        with self._lock:
            self._pulses += 1

    @property
    def total_pulses(self) -> int:
        with self._lock:
            return self._pulses

    def reset(self) -> None:
        with self._lock:
            self._pulses = 0


class RealLed:
    """LED de estado simple. Por ahora solo usa un GPIO ON/OFF según el color.
    Para WS2812 RGB se hará una iteración futura con la librería rpi-ws281x."""

    _ON_COLORS = {LedColor.idle, LedColor.armed, LedColor.dispensing, LedColor.success}

    def __init__(self, gpio: int) -> None:
        self._dev = DigitalOutputDevice(gpio, pin_factory=_pin_factory)

    def set(self, color: LedColor) -> None:
        if color in self._ON_COLORS:
            self._dev.on()
        else:
            self._dev.off()
