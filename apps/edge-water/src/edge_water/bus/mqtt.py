from __future__ import annotations

import asyncio
import ssl
from contextlib import AsyncExitStack

import aiomqtt
from loguru import logger

from edge_water.bus.base import Bus, MessageHandler, topic_matches


class MqttBus(Bus):
    """Bus respaldado por un broker MQTT real (vía aiomqtt)."""

    def __init__(
        self,
        host: str,
        port: int = 1883,
        *,
        username: str | None = None,
        password: str | None = None,
        tls: bool = False,
        client_id: str | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._tls = tls
        self._client_id = client_id

        self._stack: AsyncExitStack | None = None
        self._client: aiomqtt.Client | None = None
        self._listener: asyncio.Task[None] | None = None
        self._subscriptions: list[tuple[str, MessageHandler]] = []

    async def start(self) -> None:
        self._stack = AsyncExitStack()
        tls_ctx = ssl.create_default_context() if self._tls else None
        client = aiomqtt.Client(
            hostname=self._host,
            port=self._port,
            username=self._username,
            password=self._password,
            tls_context=tls_ctx,
            identifier=self._client_id,
        )
        self._client = await self._stack.enter_async_context(client)
        self._listener = asyncio.create_task(self._dispatch_loop(), name="mqtt-dispatch")
        logger.info("MQTT conectado a {}:{}", self._host, self._port)

    async def stop(self) -> None:
        if self._listener:
            self._listener.cancel()
            try:
                await self._listener
            except (asyncio.CancelledError, Exception):
                pass
        if self._stack:
            await self._stack.aclose()
        self._listener = None
        self._client = None
        self._stack = None

    async def publish(self, topic: str, payload: bytes) -> None:
        if not self._client:
            raise RuntimeError("MqttBus no iniciado")
        await self._client.publish(topic, payload, qos=1)

    async def subscribe(self, topic_pattern: str, handler: MessageHandler) -> None:
        if not self._client:
            raise RuntimeError("MqttBus no iniciado")
        self._subscriptions.append((topic_pattern, handler))
        await self._client.subscribe(topic_pattern, qos=1)

    async def _dispatch_loop(self) -> None:
        assert self._client is not None
        async for message in self._client.messages:
            topic = str(message.topic)
            payload = message.payload if isinstance(message.payload, bytes) else bytes(message.payload or b"")
            for pattern, handler in self._subscriptions:
                if topic_matches(pattern, topic):
                    try:
                        await handler(topic, payload)
                    except Exception:  # noqa: BLE001
                        logger.exception("Handler MQTT falló en topic {}", topic)
