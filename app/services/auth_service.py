import logging
import re
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.exc import ProgrammingError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import AuthPrincipal, get_employee_roles, get_user_roles
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    hash_token,
    verify_and_update_password,
    verify_password,
)
from app.models.employee import Employee
from app.models.enums import AccountType, LogStatus
from app.models.refresh_token import RefreshToken
from app.models.role import Role, UserRole
from app.models.user import User
from app.schemas.auth import (
    AuthMeResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
    EmployeeLoginRequest,
    RegisterUserRequest,
    TokenResponse,
    UpdateUserProfileRequest,
    UserLoginRequest,
)
from app.services.log_service import LogService
from app.services.login_protection_service import login_protection_service

logger = logging.getLogger(__name__)


class AuthService:
    @staticmethod
    def _normalize_phone_for_uniqueness(phone: str | None) -> str | None:
        if phone is None:
            return None
        # Keep only digits to avoid duplicates with different formatting.
        digits = re.sub(r"\D", "", phone)
        if not digits:
            return None
        # Normalize common RU local prefix.
        if len(digits) == 11 and digits.startswith("8"):
            digits = "7" + digits[1:]
        return digits

    @staticmethod
    def _find_user_with_same_phone(
        db: Session,
        *,
        phone: str | None,
        exclude_user_id: int | None = None,
    ) -> User | None:
        normalized_target = AuthService._normalize_phone_for_uniqueness(phone)
        if normalized_target is None:
            return None
        candidates = db.query(User).filter(User.phone.is_not(None)).all()
        for candidate in candidates:
            if exclude_user_id is not None and candidate.user_id == exclude_user_id:
                continue
            candidate_normalized = AuthService._normalize_phone_for_uniqueness(candidate.phone)
            if candidate_normalized == normalized_target:
                return candidate
        return None

    @staticmethod
    def _auth_actor_kwargs(db: Session, *, account_type: AccountType, subject_id: int) -> dict[str, int]:
        if account_type == AccountType.USER:
            user = db.get(User, subject_id)
            if user:
                return {"actor_user_id": user.user_id}
        else:
            employee = db.get(Employee, subject_id)
            if employee:
                return {"actor_employee_id": employee.employee_id}
        return {}

    @staticmethod
    def _revoke_refresh_tokens_for_subject(db: Session, *, subject_id: int, account_type: AccountType) -> int:
        tokens = (
            db.query(RefreshToken)
            .filter(
                RefreshToken.subject_id == subject_id,
                RefreshToken.account_type == account_type,
                RefreshToken.is_revoked.is_(False),
            )
            .all()
        )
        now = datetime.now(UTC)
        for token in tokens:
            token.is_revoked = True
            token.revoked_at = now
            db.add(token)
        return len(tokens)

    @staticmethod
    def _issue_tokens(db: Session, *, subject_id: int, account_type: AccountType, roles: list[str]) -> TokenResponse:
        access_token = create_access_token(subject=subject_id, account_type=account_type.value, roles=roles)
        refresh_token = create_refresh_token(subject=subject_id, account_type=account_type.value, roles=roles)
        refresh_record = RefreshToken(
            subject_id=subject_id,
            account_type=account_type,
            token_hash=hash_token(refresh_token),
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
        )
        db.add(refresh_record)
        try:
            db.flush()
        except ProgrammingError as exc:
            db.rollback()
            if "refresh_tokens" in str(exc).lower():
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Database schema is outdated: missing table refresh_tokens. Run `alembic upgrade head`.",
                ) from exc
            raise
        return TokenResponse(access_token=access_token, refresh_token=refresh_token)

    @staticmethod
    def register_user(db: Session, payload: RegisterUserRequest) -> User:
        normalized_email = str(payload.email).strip().lower()
        exists = db.query(User).filter(func.lower(User.email) == normalized_email).first()
        if exists:
            logger.warning("Registration failed: email already exists: %s", normalized_email)
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
        duplicate_phone_user = AuthService._find_user_with_same_phone(db, phone=payload.phone)
        if duplicate_phone_user:
            logger.warning("Registration failed: phone already exists")
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phone already registered")

        user = User(
            username=payload.username,
            email=normalized_email,
            password_hash=get_password_hash(payload.password),
            phone=payload.phone,
            is_active=True,
        )
        db.add(user)
        db.flush()

        user_role = db.query(Role).filter(Role.role_code == "USER").first()
        if user_role is not None:
            db.add(UserRole(user_id=user.user_id, role_id=user_role.role_id))

        LogService.log_action(
            db,
            actor_user_id=user.user_id,
            user_role="USER",
            action_type="REGISTER",
            entity_type="users",
            entity_id=str(user.user_id),
            status=LogStatus.SUCCESS,
            details={"email": user.email},
        )
        db.commit()
        db.refresh(user)
        logger.info("User registered: %s", user.email)
        return user

    @staticmethod
    def login_user(db: Session, payload: UserLoginRequest, *, client_ip: str = "unknown") -> TokenResponse:
        normalized_email = payload.email.strip().lower()
        login_key = f"user:{normalized_email}:{client_ip}"
        blocked_seconds = login_protection_service.check_blocked_seconds(login_key)
        if blocked_seconds > 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many failed attempts. Try again in {blocked_seconds} seconds.",
            )

        user = db.query(User).filter(User.email == normalized_email).first()

        if not user:
            login_protection_service.register_failure(login_key)
            logger.warning("User login failed: user not found for email=%s", payload.email)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        verified, replacement_hash = verify_and_update_password(payload.password, user.password_hash)
        if not verified:
            blocked_seconds = login_protection_service.register_failure(login_key)
            LogService.log_action(
                db,
                actor_user_id=user.user_id,
                user_role="USER",
                action_type="LOGIN",
                entity_type="users",
                entity_id=str(user.user_id),
                status=LogStatus.FAILED,
                message="Invalid password",
                details={"blocked_seconds": blocked_seconds} if blocked_seconds > 0 else None,
            )
            db.commit()
            logger.warning("User login failed: invalid password for user_id=%s email=%s", user.user_id, payload.email)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        if replacement_hash:
            user.password_hash = replacement_hash
            db.add(user)
        if not user.is_active:
            logger.warning("User login blocked (inactive): user_id=%s", user.user_id)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")

        login_protection_service.register_success(login_key)
        roles = get_user_roles(db, user.user_id)
        token_response = AuthService._issue_tokens(
            db,
            subject_id=user.user_id,
            account_type=AccountType.USER,
            roles=roles,
        )
        LogService.log_action(
            db,
            actor_user_id=user.user_id,
            user_role=roles[0] if roles else "USER",
            action_type="LOGIN",
            entity_type="users",
            entity_id=str(user.user_id),
            status=LogStatus.SUCCESS,
        )
        db.commit()
        logger.info("User login success: user_id=%s", user.user_id)
        return token_response

    @staticmethod
    def login_employee(db: Session, payload: EmployeeLoginRequest, *, client_ip: str = "unknown") -> TokenResponse:
        normalized_key = payload.employee_key.strip().upper()
        login_key = f"employee:{normalized_key}:{client_ip}"
        blocked_seconds = login_protection_service.check_blocked_seconds(login_key)
        if blocked_seconds > 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many failed attempts. Try again in {blocked_seconds} seconds.",
            )

        employee = db.query(Employee).filter(Employee.employee_key == normalized_key).first()

        if not employee:
            login_protection_service.register_failure(login_key)
            logger.warning("Employee login failed: employee not found for key=%s", payload.employee_key)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        verified, replacement_hash = verify_and_update_password(payload.password, employee.password_hash)
        if not verified:
            blocked_seconds = login_protection_service.register_failure(login_key)
            LogService.log_action(
                db,
                actor_employee_id=employee.employee_id,
                user_role="EMPLOYEE",
                action_type="EMPLOYEE_LOGIN",
                entity_type="employees",
                entity_id=str(employee.employee_id),
                status=LogStatus.FAILED,
                message="Invalid password",
                details={"blocked_seconds": blocked_seconds} if blocked_seconds > 0 else None,
            )
            db.commit()
            logger.warning(
                "Employee login failed: invalid password for employee_id=%s key=%s",
                employee.employee_id,
                payload.employee_key,
            )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        if replacement_hash:
            employee.password_hash = replacement_hash
            db.add(employee)
        if not employee.is_active:
            logger.warning("Employee login blocked (inactive): employee_id=%s", employee.employee_id)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employee is inactive")

        login_protection_service.register_success(login_key)
        roles = get_employee_roles(db, employee.employee_id)
        token_response = AuthService._issue_tokens(
            db,
            subject_id=employee.employee_id,
            account_type=AccountType.EMPLOYEE,
            roles=roles,
        )
        LogService.log_action(
            db,
            actor_employee_id=employee.employee_id,
            user_role=roles[0] if roles else "EMPLOYEE",
            action_type="EMPLOYEE_LOGIN",
            entity_type="employees",
            entity_id=str(employee.employee_id),
            status=LogStatus.SUCCESS,
        )
        db.commit()
        logger.info("Employee login success: employee_id=%s", employee.employee_id)
        return token_response

    @staticmethod
    def refresh_tokens(db: Session, refresh_token: str) -> TokenResponse:
        try:
            payload = decode_token(refresh_token)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

        subject_id = int(payload["sub"])
        account_type = AccountType(payload["account_type"])
        roles = payload.get("roles", [])
        actor_kwargs = AuthService._auth_actor_kwargs(db, account_type=account_type, subject_id=subject_id)
        actor_role = roles[0] if isinstance(roles, list) and roles else account_type.value

        token_hash = hash_token(refresh_token)
        token_record = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
        if not token_record or token_record.is_revoked:
            LogService.log_action(
                db,
                user_role=actor_role,
                action_type="REFRESH_TOKEN",
                entity_type="refresh_tokens",
                entity_id=token_hash[:12],
                status=LogStatus.FAILED,
                message="Refresh token revoked",
                **actor_kwargs,
            )
            db.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked")
        if token_record.expires_at < datetime.now(UTC):
            LogService.log_action(
                db,
                user_role=actor_role,
                action_type="REFRESH_TOKEN",
                entity_type="refresh_tokens",
                entity_id=str(token_record.token_id),
                status=LogStatus.FAILED,
                message="Refresh token expired",
                **actor_kwargs,
            )
            db.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

        token_record.is_revoked = True
        token_record.revoked_at = datetime.now(UTC)
        db.add(token_record)

        token_response = AuthService._issue_tokens(
            db,
            subject_id=subject_id,
            account_type=account_type,
            roles=roles if isinstance(roles, list) else [],
        )
        LogService.log_action(
            db,
            user_role=actor_role,
            action_type="REFRESH_TOKEN",
            entity_type="refresh_tokens",
            entity_id=str(token_record.token_id),
            status=LogStatus.SUCCESS,
            **actor_kwargs,
        )
        db.commit()
        return token_response

    @staticmethod
    def logout(db: Session, refresh_token: str) -> None:
        token_hash = hash_token(refresh_token)
        token_record = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
        if token_record and not token_record.is_revoked:
            token_record.is_revoked = True
            token_record.revoked_at = datetime.now(UTC)
            db.add(token_record)
        actor_kwargs: dict[str, int] = {}
        actor_role = "UNKNOWN"
        try:
            payload = decode_token(refresh_token)
            subject_id = int(payload.get("sub"))
            account_type = AccountType(payload.get("account_type"))
            roles = payload.get("roles", [])
            actor_role = roles[0] if isinstance(roles, list) and roles else account_type.value
            actor_kwargs = AuthService._auth_actor_kwargs(db, account_type=account_type, subject_id=subject_id)
        except Exception:  # noqa: BLE001
            pass

        LogService.log_action(
            db,
            user_role=actor_role,
            action_type="LOGOUT",
            entity_type="refresh_tokens",
            entity_id=str(token_record.token_id) if token_record else token_hash[:12],
            status=LogStatus.SUCCESS,
            **actor_kwargs,
        )
        db.commit()

    @staticmethod
    def change_password(
        db: Session,
        *,
        principal: AuthPrincipal,
        payload: ChangePasswordRequest,
    ) -> ChangePasswordResponse:
        user: User | None = None
        employee: Employee | None = None
        if principal.account_type == AccountType.USER:
            user = db.get(User, principal.subject_id)
            if not user or not user.is_active:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive or missing user")
            account_hash = user.password_hash
            actor_kwargs = {"actor_user_id": user.user_id}
            roles = get_user_roles(db, user.user_id)
            actor_role = roles[0] if roles else "USER"
            entity_type = "users"
            entity_id = str(user.user_id)
        else:
            employee = db.get(Employee, principal.subject_id)
            if not employee or not employee.is_active:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive or missing employee")
            account_hash = employee.password_hash
            actor_kwargs = {"actor_employee_id": employee.employee_id}
            roles = get_employee_roles(db, employee.employee_id)
            actor_role = roles[0] if roles else "EMPLOYEE"
            entity_type = "employees"
            entity_id = str(employee.employee_id)

        if not verify_password(payload.current_password, account_hash):
            LogService.log_action(
                db,
                user_role=actor_role,
                action_type="CHANGE_PASSWORD",
                entity_type=entity_type,
                entity_id=entity_id,
                status=LogStatus.FAILED,
                message="Invalid current password",
                **actor_kwargs,
            )
            db.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid current password")

        if verify_password(payload.new_password, account_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be different from current password",
            )

        new_hash = get_password_hash(payload.new_password)
        if user is not None:
            user.password_hash = new_hash
            db.add(user)
        elif employee is not None:
            employee.password_hash = new_hash
            db.add(employee)

        revoked_count = AuthService._revoke_refresh_tokens_for_subject(
            db,
            subject_id=principal.subject_id,
            account_type=principal.account_type,
        )
        LogService.log_action(
            db,
            user_role=actor_role,
            action_type="CHANGE_PASSWORD",
            entity_type=entity_type,
            entity_id=entity_id,
            status=LogStatus.SUCCESS,
            details={"revoked_refresh_tokens": revoked_count},
            **actor_kwargs,
        )
        db.commit()
        logger.info(
            "Password changed: account_type=%s subject_id=%s revoked_refresh_tokens=%s",
            principal.account_type,
            principal.subject_id,
            revoked_count,
        )
        return ChangePasswordResponse(
            changed=True,
            revoked_refresh_tokens=revoked_count,
            message="Password changed successfully. Please login again on other devices.",
        )

    @staticmethod
    def update_user_profile(db: Session, *, user: User, payload: UpdateUserProfileRequest) -> AuthMeResponse:
        changed_fields: list[str] = []
        fields_set = payload.model_fields_set

        if "username" in fields_set:
            if payload.username is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username cannot be empty")
            user.username = payload.username
            changed_fields.append("username")

        if "email" in fields_set:
            if payload.email is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email cannot be empty")
            normalized_email = str(payload.email).strip().lower()
            exists = (
                db.query(User)
                .filter(
                    func.lower(User.email) == normalized_email,
                    User.user_id != user.user_id,
                )
                .first()
            )
            if exists:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
            user.email = normalized_email
            changed_fields.append("email")

        if "phone" in fields_set:
            duplicate_phone_user = AuthService._find_user_with_same_phone(
                db,
                phone=payload.phone,
                exclude_user_id=user.user_id,
            )
            if duplicate_phone_user:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phone already registered")
            user.phone = payload.phone
            changed_fields.append("phone")

        if not changed_fields:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No changes to apply")

        db.add(user)
        roles = get_user_roles(db, user.user_id)
        LogService.log_action(
            db,
            actor_user_id=user.user_id,
            user_role=roles[0] if roles else "USER",
            action_type="UPDATE_USER_PROFILE",
            entity_type="users",
            entity_id=str(user.user_id),
            status=LogStatus.SUCCESS,
            details={"changed_fields": changed_fields},
        )
        db.commit()
        db.refresh(user)
        logger.info("User profile updated: user_id=%s fields=%s", user.user_id, ",".join(changed_fields))
        return AuthService.me_for_user(db, user)

    @staticmethod
    def me_for_user(db: Session, user: User) -> AuthMeResponse:
        roles = get_user_roles(db, user.user_id)
        return AuthMeResponse(
            account_type=AccountType.USER,
            subject_id=user.user_id,
            username=user.username,
            email=user.email,
            phone=user.phone,
            roles=roles,
            is_active=user.is_active,
            created_at=user.created_at,
        )

    @staticmethod
    def me_for_employee(db: Session, employee: Employee) -> AuthMeResponse:
        roles = get_employee_roles(db, employee.employee_id)
        return AuthMeResponse(
            account_type=AccountType.EMPLOYEE,
            subject_id=employee.employee_id,
            employee_key=employee.employee_key,
            email=employee.email,
            roles=roles,
            is_active=employee.is_active,
            created_at=employee.created_at,
        )
