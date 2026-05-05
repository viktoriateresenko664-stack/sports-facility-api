from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import AuthPrincipal, get_current_principal, get_current_user, require_roles
from app.db.session import get_db
from app.models.employee import Employee
from app.models.enums import AccountType
from app.models.user import User
from app.schemas.auth import (
    AuthMeResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
    EmployeeLoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    RegisterUserRequest,
    TokenResponse,
    UpdateUserProfileRequest,
    UserLoginRequest,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
AUTH_RESPONSES = {
    400: {"description": "Bad Request"},
    401: {"description": "Unauthorized"},
    403: {"description": "Forbidden"},
    404: {"description": "Not Found"},
    409: {"description": "Conflict"},
}


@router.post(
    "/register",
    response_model=AuthMeResponse,
    responses=AUTH_RESPONSES,
    summary="Register User",
    description="Creates a new user account and returns profile information.",
)
def register_user(payload: RegisterUserRequest, db: Session = Depends(get_db)) -> AuthMeResponse:
    user = AuthService.register_user(db, payload)
    return AuthService.me_for_user(db, user)


@router.post(
    "/login",
    response_model=TokenResponse,
    responses=AUTH_RESPONSES,
    summary="User Login",
    description="Authenticates a user by email and password and returns an access token.",
)
def login_user(
    payload: UserLoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    client_ip = request.client.host if request.client else "unknown"
    return AuthService.login_user(db, payload, client_ip=client_ip)


@router.post(
    "/employee-login",
    response_model=TokenResponse,
    responses=AUTH_RESPONSES,
    summary="Employee Login",
    description="Authenticates an employee and returns an access token.",
)
def login_employee(
    payload: EmployeeLoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    client_ip = request.client.host if request.client else "unknown"
    return AuthService.login_employee(db, payload, client_ip=client_ip)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    responses=AUTH_RESPONSES,
    summary="Refresh Tokens",
    description="Issues new access and refresh tokens using valid refresh token.",
)
def refresh_tokens(payload: RefreshTokenRequest, db: Session = Depends(get_db)) -> TokenResponse:
    return AuthService.refresh_tokens(db, payload.refresh_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=AUTH_RESPONSES,
    summary="Logout",
    description="Revokes provided refresh token.",
)
def logout(payload: LogoutRequest, db: Session = Depends(get_db)) -> None:
    AuthService.logout(db, payload.refresh_token)


@router.post(
    "/change-password",
    response_model=ChangePasswordResponse,
    responses=AUTH_RESPONSES,
    summary="Change Current Account Password",
    description="Changes password for the authenticated user or employee account and revokes refresh sessions.",
)
def change_password(
    payload: ChangePasswordRequest,
    principal: AuthPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> ChangePasswordResponse:
    return AuthService.change_password(db, principal=principal, payload=payload)


@router.get(
    "/me",
    response_model=AuthMeResponse,
    responses=AUTH_RESPONSES,
    summary="Get Current Profile",
    description="Returns profile details for the currently authenticated user or employee.",
)
def me(principal: AuthPrincipal = Depends(get_current_principal), db: Session = Depends(get_db)) -> AuthMeResponse:
    if principal.account_type == AccountType.USER:
        user = db.get(User, principal.subject_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return AuthService.me_for_user(db, user)

    employee = db.get(Employee, principal.subject_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return AuthService.me_for_employee(db, employee)


@router.post(
    "/me",
    response_model=AuthMeResponse,
    responses=AUTH_RESPONSES,
    summary="Update Current User Profile",
    description="Updates current USER account profile fields (username, email, phone). Only own account can be changed.",
)
def update_me(
    payload: UpdateUserProfileRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_roles("USER")),
) -> AuthMeResponse:
    return AuthService.update_user_profile(db, user=user, payload=payload)
