from __future__ import annotations

from collections import defaultdict
from typing import Callable

from sqlalchemy.orm import Session

from app.domain.events import AppDomainEvent
from app.models.domain_event import DomainEvent
from app.services.domain_event_service import DomainEventService

EventHandler = Callable[[Session, DomainEvent], None]


class EventDispatcher:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        handlers = self._subscribers[event_type]
        if handler not in handlers:
            handlers.append(handler)

    def dispatch(
        self,
        db: Session,
        event: AppDomainEvent,
        *,
        commit: bool = True,
        enqueue: bool = True,
    ) -> DomainEvent:
        stored_event = DomainEventService.publish(
            db,
            event_type=event.event_type,
            aggregate_type=event.aggregate_type,
            aggregate_id=str(event.aggregate_id),
            payload=event.to_payload(),
        )
        if commit:
            db.commit()
        if enqueue:
            DomainEventService.enqueue(str(stored_event.event_id))
        return stored_event

    def run_handlers(self, db: Session, event: DomainEvent) -> int:
        handlers = self._subscribers.get(event.event_type, [])
        for handler in handlers:
            handler(db, event)
        return len(handlers)


event_dispatcher = EventDispatcher()
