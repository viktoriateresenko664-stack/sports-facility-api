import time
from collections import deque
from typing import Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import settings
from app.core.metrics import log_request_metric
from app.core.security import decode_token


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        path = request.url.path
        docs_paths = {"/docs", "/openapi.json", "/redoc"}
        if path in docs_paths:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "img-src 'self' data: https:; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "font-src 'self' https://cdn.jsdelivr.net; "
                "connect-src 'self'; "
                "frame-ancestors 'none'; "
                "base-uri 'self';"
            )
        else:
            trusted_connect_sources = ["'self'"] + [origin.strip() for origin in settings.cors_origins if origin.strip()]
            connect_src = " ".join(dict.fromkeys(trusted_connect_sources))
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'; "
                f"connect-src {connect_src}; "
                "img-src 'self' data:; "
                "script-src 'none'; "
                "style-src 'none';"
            )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=(), usb=(), interest-cohort=()"
        )
        proto = request.headers.get("x-forwarded-proto", request.url.scheme).lower()
        if proto == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        # TODO(production): replace in-memory limiter with Redis-backed limiter for multi-instance deployments.
        self.hits: dict[tuple[str, str], deque[float]] = {}
        self._cleanup_counter = 0
        self._cleanup_interval = 200
        self._max_tracked_keys = 10_000

    def _limit_for_path(self, path: str) -> int:
        if path == "/auth/login":
            return settings.rate_limit_auth_login_per_minute
        if path == "/auth/employee-login":
            return settings.rate_limit_auth_employee_login_per_minute
        if path == "/auth/register":
            return settings.rate_limit_auth_register_per_minute
        if path == "/auth/refresh":
            return settings.rate_limit_auth_login_per_minute
        return settings.rate_limit_default_per_minute

    def _cleanup_stale_keys(self, now: float) -> None:
        window_start = now - 60
        stale_keys: list[tuple[str, str]] = []
        for key, q in self.hits.items():
            while q and q[0] < window_start:
                q.popleft()
            if not q:
                stale_keys.append(key)
        for key in stale_keys:
            self.hits.pop(key, None)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        ip = request.client.host if request.client else "unknown"
        key = (ip, request.url.path)
        now = time.time()
        window_start = now - 60
        self._cleanup_counter += 1
        if self._cleanup_counter % self._cleanup_interval == 0:
            self._cleanup_stale_keys(now)
        q = self.hits.get(key)
        if q is None:
            if len(self.hits) >= self._max_tracked_keys:
                self._cleanup_stale_keys(now)
                if len(self.hits) >= self._max_tracked_keys:
                    return JSONResponse(status_code=503, content={"detail": "Rate limit storage overloaded"})
            q = deque()
            self.hits[key] = q
        while q and q[0] < window_start:
            q.popleft()
        limit = self._limit_for_path(request.url.path)
        if len(q) >= limit:
            return JSONResponse(status_code=429, content={"detail": "Too Many Requests"})
        q.append(now)
        return await call_next(request)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.enable_request_metrics:
            return await call_next(request)
        started = time.perf_counter()
        error_text = None
        status_code = 500
        response: Response
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:  # noqa: BLE001
            error_text = str(exc)
            raise
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            user_id = None
            role = None
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header.removeprefix("Bearer ").strip()
                try:
                    payload = decode_token(token)
                    user_id = int(payload.get("sub"))
                    roles = payload.get("roles", [])
                    role = roles[0] if isinstance(roles, list) and roles else None
                except Exception:  # noqa: BLE001
                    pass
            log_request_metric(
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                response_time_ms=elapsed_ms,
                user_id=user_id,
                role=role,
                records_count=None,
                error=error_text,
            )
        return response
