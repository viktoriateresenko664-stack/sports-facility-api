from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.events import RequestCreatedEvent
from app.models.user import User
from app.schemas.user_request import UserRequestCreate, UserRequestResponse
from app.services.events import event_dispatcher
from app.services.user_request_service import UserRequestService


class UserRequestCommandService:
    @staticmethod
    def create_request(
        db: Session,
        *,
        user: User,
        payload: UserRequestCreate,
    ) -> UserRequestResponse:
        request_obj = UserRequestService.create_request(db, user, payload)
        event_dispatcher.dispatch(
            db,
            RequestCreatedEvent(
                aggregate_id=str(request_obj.request_id),
                user_id=user.user_id,
                data={"facility_id": request_obj.facility_id},
            ),
        )
        return UserRequestResponse.model_validate(request_obj)
