from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from app.core.config import settings


class LoginProtectionService:
    def __init__(self) -> None:
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._blocked_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def _window_seconds(self) -> int:
        return settings.login_bruteforce_block_seconds

    def _max_attempts(self) -> int:
        return settings.login_bruteforce_max_attempts

    def _prune(self, key: str, now: float) -> None:
        window_start = now - self._window_seconds()
        q = self._attempts[key]
        while q and q[0] < window_start:
            q.popleft()
        if not q:
            self._attempts.pop(key, None)

    def check_blocked_seconds(self, key: str) -> int:
        now = time.time()
        with self._lock:
            blocked_until = self._blocked_until.get(key)
            if blocked_until is None:
                return 0
            if blocked_until <= now:
                self._blocked_until.pop(key, None)
                return 0
            return int(blocked_until - now)

    def register_failure(self, key: str) -> int:
        now = time.time()
        with self._lock:
            self._prune(key, now)
            q = self._attempts[key]
            q.append(now)
            if len(q) >= self._max_attempts():
                blocked_until = now + self._window_seconds()
                self._blocked_until[key] = blocked_until
                self._attempts.pop(key, None)
                return int(blocked_until - now)
            return 0

    def register_success(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)
            self._blocked_until.pop(key, None)


login_protection_service = LoginProtectionService()
