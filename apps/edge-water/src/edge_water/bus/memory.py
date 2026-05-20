"""
Bus pub/sub en proceso. Útil para:
- Tests (asincrónico, determinístico)
- Simulador interactivo (sin necesidad de un broker externo)

Soporta wildcards estilo MQTT: '+' (un nivel) y '#' (cero o más niveles al final).
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field

from edge_water.bus.base import MessageHandler


def _topic_to_regex(pattern: str) -> re.Pattern[str]:
    parts = []
    segments = pattern.split("/")
    for i, seg in enumerate(segments):
        if seg == "#":
            if i != len(segments) - 1:
                raise ValueError("'#' must be the last segment")
            parts.append(".*")
        elif seg == "+":
            parts.append("[^/]+")
        else:
            parts.append(re.escape(seg))
    return re.compile("^" + "/".join(parts) + "$")


@dataclass
class _Subscription:
    pattern: str
    regex: re.Pattern[str]
    handler: MessageHandler


@dataclass
class InMemoryBus:
    subs: list[_Subscription] = field(default_factory=list)
    _tasks: set[asyncio.Task[None]] = field(default_factory=set)

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        for t in list(self._tasks):
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def publish(self, topic: str, payload: bytes) -> None:
        for sub in self.subs:
            if sub.regex.match(topic):
                task = asyncio.create_task(sub.handler(topic, payload))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)

    async def subscribe(self, topic: str, handler: MessageHandler) -> None:
        self.subs.append(_Subscription(topic, _topic_to_regex(topic), handler))
