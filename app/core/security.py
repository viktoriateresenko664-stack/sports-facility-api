from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def hash_password(password: str) -> str:
    return get_password_hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def verify_and_update_password(plain_password: str, password_hash: str) -> tuple[bool, str | None]:
    verified, replacement_hash = pwd_context.verify_and_update(plain_password, password_hash)
    return bool(verified), replacement_hash


def _create_token(subject: int, account_type: str, roles: list[str], token_type: str, expires_delta: timedelta) -> str:
    expire = datetime.now(UTC) + expires_delta
    payload = {
        "sub": str(subject),
        "account_type": account_type,
        "roles": roles,
        "type": token_type,
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_access_token(subject: int, account_type: str, roles: list[str]) -> str:
    return _create_token(
        subject=subject,
        account_type=account_type,
        roles=roles,
        token_type="access",
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(subject: int, account_type: str, roles: list[str]) -> str:
    return _create_token(
        subject=subject,
        account_type=account_type,
        roles=roles,
        token_type="refresh",
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )


def hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError as exc:
        raise ValueError("Invalid token") from exc
