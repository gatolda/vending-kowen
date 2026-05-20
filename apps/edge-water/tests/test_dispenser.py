from __future__ import annotations

import asyncio

import pytest

from edge_water.hardware.mock import MockFlowMeterConfig
from edge_water.messages import (
    AbortCommand,
    DispenseCommand,
    DispenseCompleted,
    DispenseFailed,
    DispenseProgress,
    DispenseStarted,
    FailureReason,
)


def _types(events):
    return [type(e).__name__ for e in events]


@pytest.mark.asyncio
async def test_dispense_happy_path(dispenser_setup):
    d, events, _flow, led = dispenser_setup
    await d.handle_dispense(DispenseCommand(order_id="o1", liters=0.5))

    types = _types(events)
    assert types[0] == "DispenseStarted"
    assert types[-1] == "DispenseCompleted"
    completed = [e for e in events if isinstance(e, DispenseCompleted)][0]
    assert completed.order_id == "o1"
    assert completed.liters_target == 0.5
    # Tolerancia: el caudalímetro mock puede pasarse 1-2 pulsos antes del check.
    assert completed.liters_actual >= 0.5
    assert completed.liters_actual <= 0.5 * 1.05
    assert completed.duration_ms > 0
    assert led.history[-1].name == "success"


@pytest.mark.asyncio
async def test_progress_events_emitted(dispenser_setup):
    """Con caudal moderado, debe haber al menos un evento de progreso intermedio."""
    d, events, flow, _led = dispenser_setup
    # 100 pulsos/seg * 100 pulsos/L = 1 L/seg. Para 1L, al menos varios ticks de 50ms.
    flow.configure(MockFlowMeterConfig(pulses_per_second=100.0))
    await d.handle_dispense(DispenseCommand(order_id="op", liters=1.0))

    progresses = [e for e in events if isinstance(e, DispenseProgress)]
    assert len(progresses) >= 2
    assert progresses[0].percent < progresses[-1].percent


@pytest.mark.asyncio
async def test_no_flow_failure_when_stuck(dispenser_setup):
    d, events, flow, _led = dispenser_setup
    flow.configure(MockFlowMeterConfig(stuck=True))

    await d.handle_dispense(DispenseCommand(order_id="o2", liters=1.0))

    failed = [e for e in events if isinstance(e, DispenseFailed)]
    assert len(failed) == 1
    assert failed[0].reason == FailureReason.no_flow
    assert failed[0].liters_partial == 0.0


@pytest.mark.asyncio
async def test_abort_during_dispense(dispenser_setup):
    d, events, flow, _led = dispenser_setup
    # Caudal lento para tener tiempo de abortar.
    flow.configure(MockFlowMeterConfig(pulses_per_second=20.0))

    task = asyncio.create_task(d.handle_dispense(DispenseCommand(order_id="o3", liters=1.0)))
    # Espera a que arranque pero no termine.
    await asyncio.sleep(0.2)
    await d.handle_abort(AbortCommand(order_id="o3", reason="user"))
    await task

    failed = [e for e in events if isinstance(e, DispenseFailed)]
    assert len(failed) == 1
    assert failed[0].reason == FailureReason.aborted
    assert failed[0].liters_partial > 0


@pytest.mark.asyncio
async def test_idempotency_same_order_id(dispenser_setup):
    d, events, _flow, _led = dispenser_setup
    await d.handle_dispense(DispenseCommand(order_id="o4", liters=0.2))
    n_after_first = len(events)

    # Reenvío del mismo comando: NO debe dispensar de nuevo.
    await d.handle_dispense(DispenseCommand(order_id="o4", liters=0.2))
    assert len(events) == n_after_first


@pytest.mark.asyncio
async def test_busy_rejects_concurrent_order(dispenser_setup):
    d, events, flow, _led = dispenser_setup
    flow.configure(MockFlowMeterConfig(pulses_per_second=50.0))

    task = asyncio.create_task(d.handle_dispense(DispenseCommand(order_id="A", liters=2.0)))
    await asyncio.sleep(0.1)  # asegura que A esté corriendo

    # B llega mientras A está activa: debe ser rechazada con busy.
    await d.handle_dispense(DispenseCommand(order_id="B", liters=0.5))

    busy = [e for e in events if isinstance(e, DispenseFailed) and e.order_id == "B"]
    assert busy and busy[0].reason == FailureReason.busy

    await d.handle_abort(AbortCommand(order_id="A"))
    await task


@pytest.mark.asyncio
async def test_partial_dispense_then_stuck(dispenser_setup):
    d, events, flow, _led = dispenser_setup
    # Tras 30 pulsos (=0.3 L) la bomba se "atasca".
    flow.configure(MockFlowMeterConfig(pulses_per_second=300.0, stop_after_pulses=30))

    await d.handle_dispense(DispenseCommand(order_id="o5", liters=1.0))

    failed = [e for e in events if isinstance(e, DispenseFailed)]
    assert len(failed) == 1
    assert failed[0].reason == FailureReason.no_flow
    # Debe haber dispensado al menos algo (~0.3 L), pero NO el target.
    assert 0.2 < failed[0].liters_partial < 1.0


@pytest.mark.asyncio
async def test_valve_and_pump_off_after_completion(dispenser_setup):
    d, _events, flow, _led = dispenser_setup
    # Acceso al valve/pump vía el caudalímetro mock que los referencia.
    valve = flow._valve  # noqa: SLF001
    pump = flow._pump  # noqa: SLF001

    await d.handle_dispense(DispenseCommand(order_id="o6", liters=0.3))
    assert valve.is_open is False
    assert pump.is_running is False


@pytest.mark.asyncio
async def test_started_event_fields(dispenser_setup):
    d, events, _flow, _led = dispenser_setup
    await d.handle_dispense(DispenseCommand(order_id="o7", liters=0.4))
    started = [e for e in events if isinstance(e, DispenseStarted)]
    assert started and started[0].liters_target == 0.4
    assert started[0].order_id == "o7"
