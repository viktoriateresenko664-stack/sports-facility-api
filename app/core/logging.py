import logging
from logging.config import dictConfig
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


class AccessLogSanitizerFilter(logging.Filter):
    _SENSITIVE_QUERY_KEYS = {
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "auth",
        "jwt",
    }
    _ALWAYS_STRIP_QUERY_PATH_PREFIXES = ("/ws/", "/bff/mobile/events/stream")

    @classmethod
    def _sanitize_path(cls, path_with_query: str) -> str:
        split = urlsplit(path_with_query)
        path_only = split.path or path_with_query
        if not split.query:
            return path_only
        if any(path_only.startswith(prefix) for prefix in cls._ALWAYS_STRIP_QUERY_PATH_PREFIXES):
            return path_only
        sanitized_pairs: list[tuple[str, str]] = []
        for key, value in parse_qsl(split.query, keep_blank_values=True):
            if key.strip().lower() in cls._SENSITIVE_QUERY_KEYS:
                sanitized_pairs.append((key, "[REDACTED]"))
            else:
                sanitized_pairs.append((key, value))
        safe_query = urlencode(sanitized_pairs, doseq=True)
        return urlunsplit(("", "", path_only, safe_query, ""))

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str):
            mutable = list(args)
            mutable[2] = self._sanitize_path(mutable[2])
            record.args = tuple(mutable)
            return True
        if isinstance(args, dict):
            path_value = args.get("full_path") or args.get("path")
            if isinstance(path_value, str):
                sanitized_path = self._sanitize_path(path_value)
                args["full_path"] = sanitized_path
                args["path"] = sanitized_path
            request_line = args.get("request_line")
            if isinstance(request_line, str):
                parts = request_line.split(" ")
                if len(parts) >= 3:
                    parts[1] = self._sanitize_path(parts[1])
                    args["request_line"] = " ".join(parts)
            record.args = args
        return True


def _install_access_log_sanitizer() -> None:
    sanitizer = AccessLogSanitizerFilter()
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.addFilter(sanitizer)
    for handler in access_logger.handlers:
        handler.addFilter(sanitizer)


def setup_logging() -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                }
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                    "level": "INFO",
                }
            },
            "root": {
                "handlers": ["default"],
                "level": "INFO",
            },
        }
    )
    _install_access_log_sanitizer()
    logging.getLogger(__name__).info("Logging configured")
