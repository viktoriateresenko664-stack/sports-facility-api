from __future__ import annotations

from sqlalchemy.orm import Session

from app.api.deps import AuthPrincipal
from app.models.user import User
from app.schemas.auth import (
    AuthMeResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
    UpdateUserProfileRequest,
)
from app.services.auth_service import AuthService


class AuthCommandService:
    @staticmethod
    def change_password(
        db: Session,
        *,
        principal: AuthPrincipal,
        payload: ChangePasswordRequest,
    ) -> ChangePasswordResponse:
        return AuthService.change_password(db, principal=principal, payload=payload)

    @staticmethod
    def update_profile(
        db: Session,
        *,
        user: User,
        payload: UpdateUserProfileRequest,
    ) -> AuthMeResponse:
        return AuthService.update_user_profile(db, user=user, payload=payload)
