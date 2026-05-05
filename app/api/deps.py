import logging
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.employee import Employee
from app.models.enums import AccountType
from app.models.role import EmployeeRole, UserRole
from app.models.user import User

logger = logging.getLogger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


@dataclass
class AuthPrincipal:
    account_type: AccountType
    subject_id: int
    roles: list[str]


def get_current_principal(token: str = Depends(oauth2_scheme)) -> AuthPrincipal:
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise ValueError("Access token required")
        sub = int(payload.get("sub"))
        account_type = AccountType(payload.get("account_type"))
        roles = payload.get("roles", [])
        if not isinstance(roles, list):
            roles = []
        return AuthPrincipal(account_type=account_type, subject_id=sub, roles=roles)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Authorization failed: invalid token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_current_user(
    db: Session = Depends(get_db), principal: AuthPrincipal = Depends(get_current_principal)
) -> User:
    if principal.account_type != AccountType.USER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account required")
    user = db.get(User, principal.subject_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive or missing user")
    return user


def get_current_employee(
    db: Session = Depends(get_db), principal: AuthPrincipal = Depends(get_current_principal)
) -> Employee:
    if principal.account_type != AccountType.EMPLOYEE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employee account required")
    employee = db.get(Employee, principal.subject_id)
    if not employee or not employee.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive or missing employee")
    return employee


def get_user_roles(db: Session, user_id: int) -> list[str]:
    rows = (
        db.query(UserRole)
        .join(UserRole.role)
        .filter(UserRole.user_id == user_id)
        .all()
    )
    return [r.role.role_code for r in rows]


def get_employee_roles(db: Session, employee_id: int) -> list[str]:
    rows = (
        db.query(EmployeeRole)
        .join(EmployeeRole.role)
        .filter(EmployeeRole.employee_id == employee_id)
        .all()
    )
    return [r.role.role_code for r in rows]


def require_roles(*required_roles: str):
    def dependency(principal: AuthPrincipal = Depends(get_current_principal)) -> AuthPrincipal:
        if not set(required_roles).intersection(set(principal.roles)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return principal

    return dependency
