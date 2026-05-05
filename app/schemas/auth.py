from datetime import datetime
import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.enums import AccountType

PHONE_PATTERN = re.compile(r"^[0-9+()\-\s]{5,30}$")


class RegisterUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    phone: str | None = None
    model_config = ConfigDict(extra="forbid")

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = value.strip()
        if "<" in normalized or ">" in normalized:
            raise ValueError("Username contains forbidden characters")
        return normalized

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_and_validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if not PHONE_PATTERN.fullmatch(normalized):
            raise ValueError("Phone has invalid format")
        return normalized


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str
    model_config = ConfigDict(extra="forbid")


class EmployeeLoginRequest(BaseModel):
    employee_key: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    model_config = ConfigDict(extra="forbid")


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=4096)
    model_config = ConfigDict(extra="forbid")


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=4096)
    model_config = ConfigDict(extra="forbid")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    model_config = ConfigDict(extra="forbid")


class AuthMeResponse(BaseModel):
    account_type: AccountType
    subject_id: int
    username: str | None = None
    email: str | None = None
    phone: str | None = None
    employee_key: str | None = None
    roles: list[str] = []
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
    new_password_confirm: str = Field(min_length=8, max_length=128)
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_new_passwords_match(self) -> "ChangePasswordRequest":
        if self.new_password != self.new_password_confirm:
            raise ValueError("New passwords do not match")
        return self


class ChangePasswordResponse(BaseModel):
    changed: bool = True
    revoked_refresh_tokens: int = 0
    message: str = "Password changed successfully"
    model_config = ConfigDict(extra="forbid")


class UpdateUserProfileRequest(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    model_config = ConfigDict(extra="forbid")

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if normalized and ("<" in normalized or ">" in normalized):
            raise ValueError("Username contains forbidden characters")
        return normalized or None

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if normalized and not PHONE_PATTERN.fullmatch(normalized):
            raise ValueError("Phone has invalid format")
        return normalized or None

    @model_validator(mode="after")
    def validate_payload_not_empty(self) -> "UpdateUserProfileRequest":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        return self
