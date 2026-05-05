from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, ClassVar


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class AppDomainEvent:
    aggregate_id: str
    user_id: int | None = None
    timestamp: datetime = field(default_factory=_utcnow)
    data: dict[str, Any] = field(default_factory=dict)

    event_type: ClassVar[str] = "domain_event"
    aggregate_type: ClassVar[str] = "generic"

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
        }
        if self.data:
            payload["data"] = self.data
        return payload


@dataclass(slots=True)
class RequestCreatedEvent(AppDomainEvent):
    event_type: ClassVar[str] = "request_created"
    aggregate_type: ClassVar[str] = "user_requests"


@dataclass(slots=True)
class RequestAssignedEvent(AppDomainEvent):
    event_type: ClassVar[str] = "request_assigned"
    aggregate_type: ClassVar[str] = "user_requests"


@dataclass(slots=True)
class TaskCompletedEvent(AppDomainEvent):
    event_type: ClassVar[str] = "task_completed"
    aggregate_type: ClassVar[str] = "engineer_tasks"


@dataclass(slots=True)
class ReportUploadedEvent(AppDomainEvent):
    event_type: ClassVar[str] = "report_uploaded"
    aggregate_type: ClassVar[str] = "engineer_reports"


@dataclass(slots=True)
class ReportGenerationStartedEvent(AppDomainEvent):
    event_type: ClassVar[str] = "report_generation_started"
    aggregate_type: ClassVar[str] = "background_jobs"


@dataclass(slots=True)
class ReportGeneratedEvent(AppDomainEvent):
    event_type: ClassVar[str] = "report_generated"
    aggregate_type: ClassVar[str] = "engineer_reports"


__all__ = [
    "AppDomainEvent",
    "RequestAssignedEvent",
    "RequestCreatedEvent",
    "ReportGeneratedEvent",
    "ReportGenerationStartedEvent",
    "ReportUploadedEvent",
    "TaskCompletedEvent",
]
