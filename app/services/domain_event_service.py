from sqlalchemy.orm import Session

from app.models.domain_event import DomainEvent
from app.models.enums import DomainEventStatus
from app.tasks.domain_event_tasks import process_domain_event_task


class DomainEventService:
    @staticmethod
    def publish(
        db: Session,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict | None = None,
        status: DomainEventStatus = DomainEventStatus.PENDING,
    ) -> DomainEvent:
        event = DomainEvent(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
            status=status,
        )
        db.add(event)
        db.flush()
        return event

    @staticmethod
    def enqueue(event_id: str) -> None:
        process_domain_event_task.apply_async(args=[event_id], ignore_result=True)
