from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket

from app.services.mobile_event_stream_service import mobile_event_stream_service

logger = logging.getLogger(__name__)


class TaskStreamService:
    def __init__(self) -> None:
        self._clients: dict[WebSocket, dict[str, object]] = {}
        self._lock = asyncio.Lock()
        self._event_loop: asyncio.AbstractEventLoop | None = None

    @property
    def connected_clients(self) -> int:
        return len(self._clients)

    def bind_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._event_loop = loop

    async def connect(
        self,
        websocket: WebSocket,
        *,
        employee_id: int | None = None,
        privileged: bool = True,
    ) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients[websocket] = {
                "employee_id": employee_id,
                "privileged": privileged,
            }
        logger.info("Task websocket connected. clients=%s", len(self._clients))

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.pop(websocket, None)
        logger.info("Task websocket disconnected. clients=%s", len(self._clients))

    @staticmethod
    def _extract_owner_id(payload: dict[str, Any]) -> int | None:
        owner_id = payload.get("assigned_engineer_id", payload.get("engineer_id"))
        if isinstance(owner_id, int):
            return owner_id
        if isinstance(owner_id, str) and owner_id.isdigit():
            return int(owner_id)
        return None

    @classmethod
    def _should_deliver_to_client(cls, payload: dict[str, Any], client_meta: dict[str, object]) -> bool:
        privileged = bool(client_meta.get("privileged"))
        if privileged:
            return True
        employee_id = client_meta.get("employee_id")
        if not isinstance(employee_id, int):
            return False
        owner_id = cls._extract_owner_id(payload)
        if owner_id is None:
            return False
        return owner_id == employee_id

    async def broadcast_json(self, payload: dict[str, Any]) -> None:
        async with self._lock:
            clients = list(self._clients.items())

        stale_clients: list[WebSocket] = []
        for client, meta in clients:
            if not self._should_deliver_to_client(payload, meta):
                continue
            try:
                await client.send_json(payload)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Task websocket send failed: %s", exc)
                stale_clients.append(client)

        if stale_clients:
            async with self._lock:
                for client in stale_clients:
                    self._clients.pop(client, None)

    def publish_event(self, event_type: str, payload: dict[str, Any]) -> None:
        if self._event_loop is None:
            return
        event_payload: dict[str, Any] = {
            "type": event_type,
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
        event_payload.update(payload)
        asyncio.run_coroutine_threadsafe(self.broadcast_json(event_payload), self._event_loop)
        mobile_event_stream_service.publish_event(event_type, payload)


task_stream_service = TaskStreamService()
