from __future__ import annotations

import asyncio

import pytest

from edge_water.bus import InMemoryBus, topic_matches


@pytest.mark.parametrize(
    "pattern,topic,expected",
    [
        ("a/b/c", "a/b/c", True),
        ("a/b/c", "a/b/d", False),
        ("a/+/c", "a/b/c", True),
        ("a/+/c", "a/b/d", False),
        ("a/#", "a/b/c/d", True),
        ("a/#", "a", True),
        ("a/b/#", "a/b/c", True),
        ("a/b/#", "x/b/c", False),
        ("machines/+/event/#", "machines/water-1/event/heartbeat", True),
        ("machines/+/event/#", "machines/water-1/cmd/dispense", False),
    ],
)
def test_topic_matches(pattern, topic, expected):
    assert topic_matches(pattern, topic) is expected


@pytest.mark.asyncio
async def test_in_memory_bus_pub_sub():
    bus = InMemoryBus()
    await bus.start()
    received: list[tuple[str, bytes]] = []
    done = asyncio.Event()

    async def handler(topic: str, payload: bytes) -> None:
        received.append((topic, payload))
        done.set()

    await bus.subscribe("foo/+/bar", handler)
    await bus.publish("foo/x/bar", b"hello")
    await asyncio.wait_for(done.wait(), timeout=1.0)

    assert received == [("foo/x/bar", b"hello")]
    await bus.stop()


@pytest.mark.asyncio
async def test_in_memory_bus_no_match():
    bus = InMemoryBus()
    await bus.start()
    called = False

    async def handler(topic: str, payload: bytes) -> None:
        nonlocal called
        called = True

    await bus.subscribe("foo/bar", handler)
    await bus.publish("foo/baz", b"x")
    await asyncio.sleep(0.05)
    assert called is False
    await bus.stop()
