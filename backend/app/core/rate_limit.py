"""Small in-process sliding-window rate limiter.

Good enough for a single Render instance. State resets on restart, which is acceptable
because the *daily* AI quota is enforced from the database (ai_usage_events), not here.
"""

import threading
import time
from collections import defaultdict, deque

from app.core.errors import RateLimitedError


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: float = 60.0) -> None:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window_seconds:
                q.popleft()
            if len(q) >= limit:
                retry = int(window_seconds - (now - q[0])) + 1
                raise RateLimitedError(f"Too many requests. Try again in {retry}s.")
            q.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = SlidingWindowLimiter()
