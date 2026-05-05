from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from app.models.user_request import UserRequest


class UserRequestRepository:
    def create(self, db: Session, request: UserRequest) -> UserRequest:
        db.add(request)
        db.flush()
        return request

    def save(self, db: Session, request: UserRequest) -> UserRequest:
        db.add(request)
        db.commit()
        db.refresh(request)
        return request

    def get_by_id(self, db: Session, request_id: int) -> UserRequest | None:
        return db.get(UserRequest, request_id)

    def list_all(self, db: Session) -> list[UserRequest]:
        return (
            db.query(UserRequest)
            .options(
                selectinload(UserRequest.facility),
                selectinload(UserRequest.user),
                selectinload(UserRequest.engineer_task),
            )
            .order_by(UserRequest.created_at.desc())
            .all()
        )