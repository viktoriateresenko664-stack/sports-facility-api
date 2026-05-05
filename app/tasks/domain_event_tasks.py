from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.core.metrics import log_queue_metric
from app.db.session import SessionLocal
from app.models.domain_event import DomainEvent
from app.models.enums import DomainEventStatus
from app.services.events import ensure_default_subscribers, event_dispatcher
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

        ensure_default_subscribers()
        handled_subscribers = event_dispatcher.run_handlers(db, event)

        event.status = DomainEventStatus.PROCESSED
        event.processed_at = datetime.now(UTC)
        db.add(event)
        db.commit()
        log_queue_metric(queue_job_id=event_id, queue_status=event.status.value, error=None)
        return {"event_id": event_id, "status": "PROCESSED", "handled_subscribers": handled_subscribers}
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        event = db.get(DomainEvent, UUID(event_id))
        if event:
            event.status = DomainEventStatus.FAILED
            event.error = str(exc)
            event.processed_at = datetime.now(UTC)
            db.add(event)
            db.commit()
        log_queue_metric(queue_job_id=event_id, queue_status=DomainEventStatus.FAILED.value, error=str(exc))
        raise
    finally:
        db.close()
