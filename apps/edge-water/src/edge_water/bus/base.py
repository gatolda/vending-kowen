from collections.abc import Awaitable, Callable
from typing import Protocol

MessageHandler = Callable[[str, bytes], Awaitable[None]]


class Bus(Protocol):
    """Pub/sub abstraction. Two impls: InMemoryBus (sim/tests), MqttBus (prod)."""

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def publish(self, topic: str, payload: bytes) -> None: ...

    async def subscribe(self, topic: str, handler: MessageHandler) -> None:
        """Subscribe to a topic. `topic` may include MQTT wildcards (+, #)."""
        ...


def topic_matches(pattern: str, topic: str) -> bool:
    """Match estilo MQTT: '+' = un nivel, '#' = resto."""
    p = pattern.split("/")
    t = topic.split("/")
    for i, segment in enumerate(p):
        if segment == "#":
            return True
        if i >= len(t):
            return False
        if segment == "+":
            continue
        if segment != t[i]:
            return False
    return len(p) == len(t)
