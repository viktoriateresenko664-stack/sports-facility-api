from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user_request import UserRequestCreate, UserRequestResponse
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
        return UserRequestResponse.model_validate(request_obj)
