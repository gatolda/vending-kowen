"""
Interfaces de hardware. El dispensador depende SOLO de estos Protocols, nunca de GPIO directo.

Esto permite:
- Tests rápidos con MockValve/MockPump/MockFlowMeter
- Reemplazar el caudalímetro o la válvula sin tocar la lógica de negocio
- Ejecutar todo el firmware en una PC (Windows/macOS) sin Pi
"""
from __future__ import annotations

from enum import Enum
from typing import Protocol, runtime_checkable


@runtime_checkable
class Valve(Protocol):
    def open(self) -> None: ...
    def close(self) -> None: ...
    @property
    def is_open(self) -> bool: ...


@runtime_checkable
class Pump(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...
    @property
    def is_running(self) -> bool: ...


@runtime_checkable
class FlowMeter(Protocol):
    """Cuenta pulsos del caudalímetro. El conteo debe ser thread-safe (las ISR
    en GPIO ocurren en un thread separado)."""
    @property
    def total_pulses(self) -> int: ...
    def reset(self) -> None: ...


class LedColor(str, Enum):
    off = "off"
    idle = "idle"            # azul tenue / breathing
    armed = "armed"          # cyan fijo (orden recibida, esperando dispensado)
    dispensing = "dispensing"  # verde parpadeando
    success = "success"      # verde fijo unos segundos
    error = "error"          # rojo
    leak = "leak"            # rojo parpadeando rápido


@runtime_checkable
class StatusLed(Protocol):
    def set(self, color: LedColor) -> None: ...
