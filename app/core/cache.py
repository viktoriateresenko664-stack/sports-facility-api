import time
from threading import Lock
from typing import Any


class TTLCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._store.get(key)
            if not item:
                return None
            expires_at, value = item
            if expires_at < time.time():
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any, ttl_seconds: int = 30) -> None:
        with self._lock:
            self._store[key] = (time.time() + ttl_seconds, value)

    def invalidate(self, prefix: str | None = None) -> list[str]:
        with self._lock:
            if not prefix:
                keys = list(self._store.keys())
                self._store.clear()
                return keys
            keys = [k for k in self._store if k.startswith(prefix)]
            for key in keys:
                self._store.pop(key, None)
            return keys


cache = TTLCache()


def build_cache_key(*, path: str, user_id: int | None, role: str | None, account_type: str | None) -> str:
    return f"{path}|uid:{user_id or 'anon'}|role:{role or 'none'}|acct:{account_type or 'none'}"
