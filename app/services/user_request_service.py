import logging

from sqlalchemy.orm import Session

from app.core.sanitizer import sanitize_text
from app.models.enums import LogStatus, RequestStatus
from app.models.user import User
from app.models.user_request import UserRequest
from app.schemas.user_request import UserRequestCreate
from app.services.domain_event_service import DomainEventService
from app.services.log_service import LogService
from app.core.cache import cache

logger = logging.getLogger(__name__)


class UserRequestService:
    @staticmethod
    def create_request(db: Session, user: User, payload: UserRequestCreate) -> UserRequest:
        request_obj = UserRequest(
            user_id=user.user_id,
            facility_id=payload.facility_id,
            title=sanitize_text(payload.title) or "",
            description=sanitize_text(payload.description) or "",
            status=RequestStatus.CREATED,
        )
        db.add(request_obj)
        db.flush()
        LogService.log_action(
            db,
            actor_user_id=user.user_id,
            user_role="USER",
            action_type="CREATE_USER_REQUEST",
            entity_type="user_requests",
            entity_id=str(request_obj.request_id),
            status=LogStatus.SUCCESS,
            details={"facility_id": payload.facility_id},
        )
        event = DomainEventService.publish(
            db,
            event_type="USER_REQUEST_CREATED",
            aggregate_type="user_requests",
            aggregate_id=str(request_obj.request_id),
            payload={"facility_id": payload.facility_id, "user_id": user.user_id},
        )
        db.commit()
        db.refresh(request_obj)
        DomainEventService.enqueue(str(event.event_id))
        cache.invalidate(prefix="/bff/")
        logger.info("User request created: request_id=%s", request_obj.request_id)
        return request_obj

    @staticmethod
    def list_my_requests(db: Session, user_id: int) -> list[UserRequest]:
        return (
            db.query(UserRequest)
            .filter(UserRequest.user_id == user_id)
            .order_by(UserRequest.created_at.desc())
            .all()
        )
