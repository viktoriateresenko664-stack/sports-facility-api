from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class MobileEventStreamService:
    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[dict[str, Any]]] = {}
        self._lock = asyncio.Lock()
        self._event_loop: asyncio.AbstractEventLoop | None = None

    @property
    def connected_clients(self) -> int:
        return len(self._queues)

    def bind_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._event_loop = loop

    async def connect(self) -> tuple[str, asyncio.Queue[dict[str, Any]]]:
        client_id = uuid4().hex
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._queues[client_id] = queue
        logger.info("Mobile SSE connected. clients=%s", len(self._queues))
        return client_id, queue

    async def disconnect(self, client_id: str) -> None:
        async with self._lock:
            self._queues.pop(client_id, None)
        logger.info("Mobile SSE disconnected. clients=%s", len(self._queues))

    async def broadcast_json(self, payload: dict[str, Any]) -> None:
        async with self._lock:
            queues = list(self._queues.values())

        for queue in queues:
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                try:
                    _ = queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    queue.put_nowait(payload)
                except asyncio.QueueFull:
                    # Slow client: drop newest event for this queue.
                    pass

    def publish_event(self, event_type: str, payload: dict[str, Any]) -> None:
        if self._event_loop is None:
            return
        event_payload: dict[str, Any] = {
            "type": event_type,
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
        event_payload.update(payload)
        asyncio.run_coroutine_threadsafe(self.broadcast_json(event_payload), self._event_loop)


mobile_event_stream_service = MobileEventStreamService()

