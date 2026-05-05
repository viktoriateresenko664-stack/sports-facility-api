from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_employee, require_roles
from app.core.security import decode_token
from app.db.session import SessionLocal, get_db
from app.models.employee import Employee
from app.models.enums import AccountType
from app.schemas.bff import MobileTasksResponse
from app.services.mobile_event_stream_service import mobile_event_stream_service
from app.services.queries.mobile_tasks_queries import MobileTasksQueryService

router = APIRouter(prefix="/bff/mobile", tags=["bff-mobile"])


def _format_sse(payload: dict) -> str:
    event_name = str(payload.get("type") or "message")
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event_name}\ndata: {data}\n\n"


def _resolve_sse_token(*, query_token: str | None, authorization_header: str | None) -> str:
    if authorization_header and authorization_header.startswith("Bearer "):
        header_token = authorization_header.removeprefix("Bearer ").strip()
        if header_token:
            return header_token
    if query_token and query_token.strip():
        return query_token.strip()
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


def _event_belongs_to_employee(payload: dict, *, employee_id: int) -> bool:
    owner = payload.get("assigned_engineer_id", payload.get("engineer_id"))
    if isinstance(owner, int):
        return owner == employee_id
    if isinstance(owner, str) and owner.isdigit():
        return int(owner) == employee_id
    return False


@router.get(
    "/tasks",
    response_model=MobileTasksResponse,
    summary="Get Mobile Tasks View",
    description="Returns compact task-related information and quick actions for mobile clients.",
)
def mobile_tasks(
    employee_id: int | None = None,
    db: Session = Depends(get_db),
    employee: Employee = Depends(get_current_employee),
    principal=Depends(require_roles("ENGINEER")),
) -> MobileTasksResponse:
    _ = principal
    if employee_id is not None and employee_id != employee.employee_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Engineer can view only own tasks")

    return MobileTasksQueryService.get_tasks(
        db,
        employee_id=employee.employee_id,
        role="ENGINEER",
        account_type="EMPLOYEE",
    )


@router.get(
    "/events/stream",
    summary="Mobile Events Stream (SSE)",
    description=(
        "Server-Sent Events stream for mobile task updates. "
        "Events: TASK_CREATED, TASK_ASSIGNED, TASK_STARTED, TASK_COMPLETED, REPORT_READY."
    ),
)
async def mobile_events_stream(
    request: Request,
    token: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> StreamingResponse:
    raw_token = _resolve_sse_token(query_token=token, authorization_header=authorization)
    try:
        payload = decode_token(raw_token)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials") from exc

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Access token required")
    account_type = payload.get("account_type")
    if account_type != AccountType.EMPLOYEE.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employee account required")
    roles = payload.get("roles", [])
    if not isinstance(roles, list):
        roles = []
    if "ENGINEER" not in set(roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    try:
        subject_id = int(payload.get("sub"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials") from exc

    with SessionLocal() as auth_db:
        employee = auth_db.get(Employee, subject_id)
        if not employee or not employee.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive or missing employee")

    client_id, queue = await mobile_event_stream_service.connect()

    async def event_generator():  # type: ignore[no-untyped-def]
        ready_payload = {
            "type": "STREAM_READY",
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
        yield _format_sse(ready_payload)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=20.0)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                if not _event_belongs_to_employee(payload, employee_id=subject_id):
                    continue
                yield _format_sse(payload)
        finally:
            await mobile_event_stream_service.disconnect(client_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
