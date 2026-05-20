from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from pydantic import BaseModel

from edge_water.dispenser import Dispenser
from edge_water.hardware.mock import MockFlowMeter, MockFlowMeterConfig, MockLed, MockPump, MockValve

# Para tests usamos pulsos_per_liter bajo y caudal alto, así un dispensado de
# 1 L termina en pocos cientos de ms en vez de minutos.
# Importante: PPS * progress_interval debe ser pequeño en pulsos para no exceder
# OVERFLOW_PCT (5%). Con PPS=200, interval=10ms → 2 pulsos overshoot máx.
TEST_PULSES_PER_LITER = 100.0
TEST_PPS = 200.0
TEST_PROGRESS_MS = 10
TEST_NO_FLOW_S = 0.5


@pytest_asyncio.fixture
async def hardware():
    valve = MockValve()
    pump = MockPump()
    flow = MockFlowMeter(
        valve, pump, MockFlowMeterConfig(pulses_per_second=TEST_PPS)
    )
    led = MockLed()
    yield valve, pump, flow, led
    flow.shutdown()


@pytest_asyncio.fixture
async def dispenser_setup(hardware) -> AsyncIterator[tuple[Dispenser, list[BaseModel], MockFlowMeter, MockLed]]:
    valve, pump, flow, led = hardware
    events: list[BaseModel] = []

    async def emit(evt: BaseModel) -> None:
        events.append(evt)

    d = Dispenser(
        machine_id="test",
        valve=valve,
        pump=pump,
        flow_meter=flow,
        led=led,
        emit=emit,
        pulses_per_liter=TEST_PULSES_PER_LITER,
        default_timeout_s=5.0,
        no_flow_timeout_s=TEST_NO_FLOW_S,
        progress_interval_ms=TEST_PROGRESS_MS,
    )
    yield d, events, flow, led
