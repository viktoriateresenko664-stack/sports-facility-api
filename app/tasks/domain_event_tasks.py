from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.db.session import SessionLocal
from app.models.domain_event import DomainEvent
from app.models.enums import DomainEventStatus
from app.tasks.celery_app import celery_app


@celery_app.task(name="process_domain_event_task")
def process_domain_event_task(event_id: str) -> dict:
    db = SessionLocal()
    try:
        event = db.get(DomainEvent, UUID(event_id))
        if not event:
            return {"event_id": event_id, "status": "NOT_FOUND"}

        event.status = DomainEventStatus.PROCESSING
        db.add(event)
        db.commit()

        event.status = DomainEventStatus.PROCESSED
        event.processed_at = datetime.now(UTC)
        db.add(event)
        db.commit()
        return {"event_id": event_id, "status": "PROCESSED"}
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        event = db.get(DomainEvent, UUID(event_id))
        if event:
            event.status = DomainEventStatus.FAILED
            event.error = str(exc)
            event.processed_at = datetime.now(UTC)
            db.add(event)
            db.commit()
        raise
    finally:
        db.close()
