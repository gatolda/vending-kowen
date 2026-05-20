"""
End-to-end: backend simulado publica DispenseCommand al bus, escucha eventos.
Verifica que todo el wiring (bus → dispenser → eventos → bus) funciona.
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest
from pydantic import BaseModel

from edge_water.app import App, build_mock_hardware, decode_event
from edge_water.bus import InMemoryBus
from edge_water.config import Settings
from edge_water.messages import (
    CMD_DISPENSE,
    DispenseCommand,
    DispenseCompleted,
    DispenseStarted,
)


@pytest.mark.asyncio
async def test_e2e_dispense_via_bus():
    settings = Settings(
        machine_id="e2e",
        hardware_mode="mock",
        bus_mode="memory",
        pulses_per_liter=100.0,
        progress_interval_ms=30,
        no_flow_timeout_s=1.0,
        heartbeat_interval_s=3600.0,  # virtualmente off para test
    )
    bus = InMemoryBus()
    hw = build_mock_hardware()
    # Acelera el caudalímetro mock para test rápido
    hw.flow_meter._config.pulses_per_second = 1000.0  # type: ignore[attr-defined]
    app = App(settings, hw, bus)
    await app.start()

    received: list[BaseModel] = []
    completed_evt = asyncio.Event()

    async def handler(topic: str, payload: bytes) -> None:
        evt = decode_event(topic, payload)
        if evt is None:
            return
        received.append(evt)
        if isinstance(evt, DispenseCompleted):
            completed_evt.set()

    await bus.subscribe(f"{settings.topic_prefix}/event/#", handler)

    cmd = DispenseCommand(order_id="e2e-1", liters=0.5)
    await bus.publish(f"{settings.topic_prefix}/{CMD_DISPENSE}", cmd.model_dump_json().encode())

    await asyncio.wait_for(completed_evt.wait(), timeout=3.0)

    types = [type(e).__name__ for e in received]
    assert "DispenseStarted" in types
    assert "DispenseCompleted" in types
    started = [e for e in received if isinstance(e, DispenseStarted)][0]
    assert started.order_id == "e2e-1"

    await app.stop()
    hw.flow_meter.shutdown()  # type: ignore[attr-defined]
