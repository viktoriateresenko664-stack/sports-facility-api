from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Sports Facilities Monitoring API"
    app_env: str = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    secret_key: str = "change_me"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    algorithm: str = "HS256"

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/sports_monitoring"
    redis_url: str = "redis://localhost:6379/0"
    sensor_source_mode: str = "fake_only"
    sensor_simulator_enabled: bool = False
    sensor_autogen_enabled: bool = True
    enable_request_metrics: bool = False
    enable_bff_cache: bool = False
    rate_limit_default_per_minute: int = 100
    rate_limit_auth_login_per_minute: int = 5
    rate_limit_auth_employee_login_per_minute: int = 5
    rate_limit_auth_register_per_minute: int = 3
    pagination_default_limit: int = 20
    pagination_max_limit: int = 100
    login_bruteforce_max_attempts: int = 5
    login_bruteforce_block_seconds: int = 600
    enable_dev_endpoints: bool = False
    allow_localhost_origins_in_production: bool = False
    cors_origins: list[str] | str = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8081",
        "http://localhost:19006",
        "http://127.0.0.1:19006",
    ]
    cors_allow_origin_regex: str | None = None
    reports_storage_dir: str = "storage/reports"
    report_template_filename: str = "engineer_report_template.txt"
    report_upload_max_size_bytes: int = 10 * 1024 * 1024
    reports_allowed_extensions: list[str] = [
        ".pdf",
        ".doc",
        ".docx",
        ".txt",
        ".md",
        ".rtf",
        ".csv",
        ".jpg",
        ".jpeg",
        ".png",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("app_env", mode="before")
    @classmethod
    def normalize_app_env(cls, value: str) -> str:
        return str(value).strip().lower()

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str] | tuple[str, ...]) -> list[str]:
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return []
            if cleaned.startswith("[") and cleaned.endswith("]"):
                import json
                try:
                    parsed = json.loads(cleaned)
                except json.JSONDecodeError as exc:
                    raise ValueError("CORS_ORIGINS JSON format is invalid") from exc
                if not isinstance(parsed, list):
                    raise ValueError("CORS_ORIGINS JSON value must be a list")
                return [str(item).strip() for item in parsed if str(item).strip()]
            return [item.strip() for item in cleaned.split(",") if item.strip()]
        if isinstance(value, tuple):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(item).strip() for item in value if str(item).strip()]

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value: bool | str) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "debug", "dev"}:
                return True
            if normalized in {"0", "false", "no", "off", "release", "prod", "production"}:
                return False
        return bool(value)

    @field_validator("secret_key", mode="before")
    @classmethod
    def validate_secret_key_not_empty(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("SECRET_KEY must not be empty")
        return normalized

    @field_validator("reports_allowed_extensions", mode="before")
    @classmethod
    def parse_reports_allowed_extensions(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return []
            parts = [item.strip().lower() for item in cleaned.split(",") if item.strip()]
        else:
            parts = [str(item).strip().lower() for item in value if str(item).strip()]
        normalized = [ext if ext.startswith(".") else f".{ext}" for ext in parts]
        return list(dict.fromkeys(normalized))

    @field_validator("sensor_source_mode", mode="before")
    @classmethod
    def normalize_sensor_source_mode(cls, value: str) -> str:
        normalized = str(value).strip().lower()
        allowed = {"fake_only", "mixed"}
        if normalized not in allowed:
            raise ValueError(f"sensor_source_mode must be one of: {', '.join(sorted(allowed))}")
        return normalized

    @field_validator("report_upload_max_size_bytes")
    @classmethod
    def validate_report_upload_max_size_bytes(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("report_upload_max_size_bytes must be positive")
        return value

    @field_validator("pagination_default_limit", "pagination_max_limit")
    @classmethod
    def validate_pagination_limits(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("pagination limits must be positive")
        return value

    @field_validator("login_bruteforce_max_attempts", "login_bruteforce_block_seconds")
    @classmethod
    def validate_login_protection(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("login protection values must be positive")
        return value

    @model_validator(mode="after")
    def validate_pagination_consistency(self) -> "Settings":
        if self.pagination_default_limit > self.pagination_max_limit:
            raise ValueError("pagination_default_limit must be <= pagination_max_limit")
        env = self.app_env
        weak_secret_values = {"", "change_me", "change_me_to_long_random_secret", "secret", "default"}
        normalized_secret = self.secret_key.strip()
        if env in {"production", "prod"} and self.debug:
            raise ValueError("DEBUG must be false in production")
        if env in {"production", "prod"}:
            if not self.cors_origins:
                raise ValueError("CORS_ORIGINS must include explicit frontend domains in production")
            if any(origin.strip() == "*" for origin in self.cors_origins):
                raise ValueError("Wildcard CORS origin '*' is forbidden in production")
            if (
                not self.allow_localhost_origins_in_production
                and any("localhost" in origin.lower() or "127.0.0.1" in origin for origin in self.cors_origins)
            ):
                raise ValueError("Localhost origins are forbidden in production")
            if self.cors_allow_origin_regex:
                raise ValueError("CORS_ALLOW_ORIGIN_REGEX must be empty in production")
        if env in {"production", "prod", "staging", "stage"}:
            if normalized_secret.lower() in weak_secret_values or len(normalized_secret) < 32:
                raise ValueError("SECRET_KEY must be strong (>=32 chars, non-default) in non-local environments")
            if self.cors_allow_origin_regex and "ngrok" in self.cors_allow_origin_regex.lower():
                raise ValueError("CORS_ALLOW_ORIGIN_REGEX must not allow ngrok in non-local environments")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
