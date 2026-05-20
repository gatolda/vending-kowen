"""
Contratos de mensajes MQTT entre máquina (edge) y backend.

Topology:
  machines/{machine_id}/cmd/<name>     <- backend → edge (comandos)
  machines/{machine_id}/event/<name>   -> edge → backend (eventos/telemetría)

Reglas:
- Toda orden lleva `order_id`. Es la clave de idempotencia.
- Todos los timestamps son UTC en ISO-8601.
- Las cantidades de agua están en litros (float). Los pulsos son enteros.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FailureReason(str, Enum):
    timeout = "timeout"          # Excedió dispense_timeout_s
    no_flow = "no_flow"          # Sin pulsos por no_flow_timeout_s (atasco/sin agua)
    aborted = "aborted"          # Cancelado por backend
    busy = "busy"                # Llegó orden mientras otra estaba activa
    hardware = "hardware"        # Falla en abrir válvula / arrancar bomba
    overflow = "overflow"        # Pulsos > esperado por margen (válvula no cerró)


# === Comandos: backend → edge ===

class DispenseCommand(BaseModel):
    """Pedir a la máquina dispensar N litros para una orden ya pagada."""
    order_id: str
    liters: float = Field(gt=0, le=20)
    timeout_s: float | None = Field(default=None, gt=0, le=600)


class AbortCommand(BaseModel):
    """Cancelar orden en curso (devuelve dinero, cierra válvula)."""
    order_id: str
    reason: str | None = None


# === Eventos: edge → backend ===

class _Event(BaseModel):
    ts: datetime = Field(default_factory=_utcnow)
    machine_id: str


class DispenseStarted(_Event):
    type: Literal["dispense_started"] = "dispense_started"
    order_id: str
    liters_target: float


class DispenseProgress(_Event):
    type: Literal["dispense_progress"] = "dispense_progress"
    order_id: str
    liters_so_far: float
    pulses: int
    percent: float


class DispenseCompleted(_Event):
    type: Literal["dispense_completed"] = "dispense_completed"
    order_id: str
    liters_target: float
    liters_actual: float
    duration_ms: int


class DispenseFailed(_Event):
    type: Literal["dispense_failed"] = "dispense_failed"
    order_id: str
    reason: FailureReason
    liters_partial: float
    detail: str | None = None


class Heartbeat(_Event):
    type: Literal["heartbeat"] = "heartbeat"
    uptime_s: float
    firmware_version: str
    state: Literal["idle", "dispensing"]


class LeakDetected(_Event):
    """Pulsos del caudalímetro mientras la máquina está IDLE → válvula fallando o tampering."""
    type: Literal["leak_detected"] = "leak_detected"
    pulses: int
    liters_estimated: float


class Telemetry(_Event):
    """Telemetría periódica (nivel del estanque, etc.)."""
    type: Literal["telemetry"] = "telemetry"
    liters_remaining: float | None = None
    temperature_c: float | None = None


# === Topics ===

CMD_DISPENSE = "cmd/dispense"
CMD_ABORT = "cmd/abort"

EVT_DISPENSE_STARTED = "event/dispense_started"
EVT_DISPENSE_PROGRESS = "event/dispense_progress"
EVT_DISPENSE_COMPLETED = "event/dispense_completed"
EVT_DISPENSE_FAILED = "event/dispense_failed"
EVT_HEARTBEAT = "event/heartbeat"
EVT_LEAK = "event/leak_detected"
EVT_TELEMETRY = "event/telemetry"
