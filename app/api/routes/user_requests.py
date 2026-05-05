from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.user_request import UserRequestCreate, UserRequestResponse
from app.services.user_request_service import UserRequestService

router = APIRouter(prefix="/user-requests", tags=["user-requests"])
USER_REQUEST_RESPONSES = {
    400: {"description": "Bad Request"},
    401: {"description": "Unauthorized"},
    403: {"description": "Forbidden"},
    404: {"description": "Not Found"},
    409: {"description": "Conflict"},
}


@router.post(
    "",
    response_model=UserRequestResponse,
    responses=USER_REQUEST_RESPONSES,
    summary="Create User Request",
    description="Creates a new maintenance request from the authenticated user.",
)
def create_user_request(
    payload: UserRequestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_roles("USER")),
) -> UserRequestResponse:
    request_obj = UserRequestService.create_request(db, user, payload)
    return UserRequestResponse.model_validate(request_obj)


@router.get(
    "/my",
    response_model=list[UserRequestResponse],
    responses=USER_REQUEST_RESPONSES,
    summary="List My Requests",
    description="Returns all requests created by the authenticated user.",
)
def list_my_requests(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_roles("USER")),
) -> list[UserRequestResponse]:
    rows = UserRequestService.list_my_requests(db, user.user_id)
    return [UserRequestResponse.model_validate(row) for row in rows]
