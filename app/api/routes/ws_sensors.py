from __future__ import annotations

import json

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.employee import Employee
from app.models.enums import AccountType
from app.services.sensor_stream_service import sensor_stream_service

router = APIRouter(tags=["ws-sensors"])
ALLOWED_WS_ROLES = {"OPERATOR", "CHIEF_ENGINEER"}


def _resolve_ws_token(websocket: WebSocket) -> str | None:
    auth_header = websocket.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.removeprefix("Bearer ").strip()
        if token:
            return token
    query_token = websocket.query_params.get("token")
    if query_token and query_token.strip():
        return query_token.strip()
    return None


def _validate_ws_token(token: str, db: Session) -> tuple[bool, str]:
    try:
        payload = decode_token(token)
        token_type = payload.get("type")
        account_type = payload.get("account_type")
        subject_id = int(payload.get("sub"))
        roles = payload.get("roles", [])
        if not isinstance(roles, list):
            roles = []
    except Exception:  # noqa: BLE001
        return False, "invalid token"

    if token_type != "access":
        return False, "access token required"
    if account_type != AccountType.EMPLOYEE.value:
        return False, "employee account required"
    if not set(roles).intersection(ALLOWED_WS_ROLES):
        return False, "insufficient role"

    employee = db.get(Employee, subject_id)
    if not employee or not employee.is_active:
        return False, "inactive employee"

    return True, ""


@router.websocket("/ws/sensors")
async def ws_sensors(websocket: WebSocket, db: Session = Depends(get_db)) -> None:
    token = _resolve_ws_token(websocket)
    if not token:
        await websocket.close(code=1008, reason="missing token")
        return

    is_valid, reason = _validate_ws_token(token, db)
    if not is_valid:
        await websocket.close(code=1008, reason=reason)
        return

    await sensor_stream_service.connect(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if payload.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        await sensor_stream_service.disconnect(websocket)
