from __future__ import annotations

from app.models.enums import RequestStatus, TaskStatus

ALERT_STATUS_NORMALIZED = {"NORMAL", "WARNING", "CRITICAL"}
ACTIVITY_STATUS_NORMALIZED = {"ACTIVE", "INACTIVE"}

_TASK_STATUS_ALIASES = {
    "CREATED": TaskStatus.CREATED.value,
    "ACTIVE": TaskStatus.ACTIVE.value,
    "IN_PROGRESS": TaskStatus.ACTIVE.value,
    "IN_WORK": TaskStatus.ACTIVE.value,
    "STARTED": TaskStatus.ACTIVE.value,
    "COMPLETED": TaskStatus.COMPLETED.value,
    "DONE": TaskStatus.COMPLETED.value,
    "CANCELLED": TaskStatus.CANCELLED.value,
    "CANCELED": TaskStatus.CANCELLED.value,
}

_REQUEST_STATUS_ALIASES = {
    "CREATED": RequestStatus.CREATED.value,
    "ACTIVE": RequestStatus.ACTIVE.value,
    "ASSIGNED": RequestStatus.ASSIGNED.value,
    "IN_WORK": RequestStatus.IN_WORK.value,
    "IN_PROGRESS": RequestStatus.IN_WORK.value,
    "STARTED": RequestStatus.IN_WORK.value,
    "COMPLETED": RequestStatus.COMPLETED.value,
    "DONE": RequestStatus.COMPLETED.value,
    "CANCELLED": RequestStatus.CANCELLED.value,
    "CANCELED": RequestStatus.CANCELLED.value,
}

_ALERT_STATUS_ALIASES = {
    "NORMAL": "NORMAL",
    "OK": "NORMAL",
    "NORM": "NORMAL",
    "НОРМАЛЬНО": "NORMAL",
    "WARNING": "WARNING",
    "WARN": "WARNING",
    "ALERT": "WARNING",
    "CRITICAL": "CRITICAL",
    "CRIT": "CRITICAL",
}

_ACTIVITY_STATUS_ALIASES = {
    "ACTIVE": "ACTIVE",
    "ENABLED": "ACTIVE",
    "INACTIVE": "INACTIVE",
    "DISABLED": "INACTIVE",
}


def _normalize_key(value: str) -> str:
    return value.strip().replace("-", "_").replace(" ", "_").upper()


def normalize_task_status(value: str | None) -> str | None:
    if value is None:
        return None
    return _TASK_STATUS_ALIASES.get(_normalize_key(value))


def normalize_request_status(value: str | None) -> str | None:
    if value is None:
        return None
    return _REQUEST_STATUS_ALIASES.get(_normalize_key(value))


def normalize_alert_status(value: str | None) -> str | None:
    if value is None:
        return None
    return _ALERT_STATUS_ALIASES.get(_normalize_key(value))


def normalize_activity_status(value: str | None) -> str | None:
    if value is None:
        return None
    return _ACTIVITY_STATUS_ALIASES.get(_normalize_key(value))
