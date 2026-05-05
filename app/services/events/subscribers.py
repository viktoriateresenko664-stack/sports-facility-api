from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.cache import cache
from app.models.domain_event import DomainEvent
from app.services.events.event_dispatcher import event_dispatcher

logger = logging.getLogger(__name__)
_is_registered = False


def _invalidate_cache(prefixes: list[str]) -> None:
    for prefix in prefixes:
        cache.invalidate(prefix=prefix)


def _handle_request_created(_db: Session, event: DomainEvent) -> None:
    _invalidate_cache(
        [
            "/bff/web/dashboard",
            "/bff/web/user-requests/my",
            "/bff/",
        ]
    )
    logger.info("Domain event handled: event_type=%s aggregate_id=%s", event.event_type, event.aggregate_id)


def _handle_request_assigned(_db: Session, event: DomainEvent) -> None:
    _invalidate_cache(
        [
            "/bff/desktop/dashboard",
            "/bff/desktop/requests",
            "/bff/mobile/tasks",
            "/bff/",
        ]
    )
    logger.info("Domain event handled: event_type=%s aggregate_id=%s", event.event_type, event.aggregate_id)


def _handle_task_completed(_db: Session, event: DomainEvent) -> None:
    _invalidate_cache(
        [
            "/bff/mobile/tasks",
            "/bff/desktop/dashboard",
            "/bff/",
        ]
    )
    logger.info("Domain event handled: event_type=%s aggregate_id=%s", event.event_type, event.aggregate_id)


def _handle_report_uploaded(_db: Session, event: DomainEvent) -> None:
    _invalidate_cache(
        [
            "/bff/desktop/reports",
            "/reports/my",
            "/bff/",
        ]
    )
    logger.info("Domain event handled: event_type=%s aggregate_id=%s", event.event_type, event.aggregate_id)


def _handle_report_generation_started(_db: Session, event: DomainEvent) -> None:
    _invalidate_cache(
        [
            "/reports/jobs",
            "/bff/desktop/reports",
            "/bff/",
        ]
    )
    logger.info("Domain event handled: event_type=%s aggregate_id=%s", event.event_type, event.aggregate_id)


def _handle_report_generated(_db: Session, event: DomainEvent) -> None:
    _invalidate_cache(
        [
            "/bff/desktop/reports",
            "/reports/my",
            "/bff/mobile/tasks",
            "/bff/",
        ]
    )
    logger.info("Domain event handled: event_type=%s aggregate_id=%s", event.event_type, event.aggregate_id)


def ensure_default_subscribers() -> None:
    global _is_registered
    if _is_registered:
        return
    event_dispatcher.subscribe("request_created", _handle_request_created)
    event_dispatcher.subscribe("request_assigned", _handle_request_assigned)
    event_dispatcher.subscribe("task_completed", _handle_task_completed)
    event_dispatcher.subscribe("report_uploaded", _handle_report_uploaded)
    event_dispatcher.subscribe("report_generation_started", _handle_report_generation_started)
    event_dispatcher.subscribe("report_generated", _handle_report_generated)
    _is_registered = True
