"""Per-Customer rate limiting (CONTEXT.md's literal "per-Customer rate
limiting" wording) — sliding-window log, business-agnostic. Not a
per-Business Config field: rate limiting isn't one of the per-Business
axes the schema defines, it's shared process policy.
"""

import threading
import time
from collections.abc import Callable

_SWEEP_INTERVAL = 500
_WINDOW_SECONDS = 60


class RateLimiter:
    """``threading.Lock``-protected: Starlette runs sync handlers in a
    thread pool, so concurrent requests can hit the same key.

    ``last_seen`` tracks idle keys for the same reason the Session Store
    and Dedupe Store need TTL eviction: a Customer key, once seen, would
    otherwise never leave the dict even after its timestamp list empties.
    Unlike Dedupe's insertion-order trick, rate-limit keys get touched
    repeatedly, so eviction can't just pop from the front — instead, every
    ``_SWEEP_INTERVAL`` calls to ``allow()`` does one O(n) pass dropping
    keys idle past ``idle_ttl_seconds``.
    """

    def __init__(
        self,
        max_per_minute: int = 20,
        idle_ttl_seconds: float = 3600,
        now_fn: Callable[[], float] = time.time,
    ) -> None:
        self._max_per_minute = max_per_minute
        self._idle_ttl_seconds = idle_ttl_seconds
        self._now_fn = now_fn
        self._timestamps: dict[str, list[float]] = {}
        self._last_seen: dict[str, float] = {}
        self._lock = threading.Lock()
        self._call_count = 0

    def allow(self, key: str) -> bool:
        now = self._now_fn()
        with self._lock:
            window_start = now - _WINDOW_SECONDS
            timestamps = [t for t in self._timestamps.get(key, []) if t > window_start]
            allowed = len(timestamps) < self._max_per_minute
            if allowed:
                timestamps.append(now)
            self._timestamps[key] = timestamps
            self._last_seen[key] = now

            self._call_count += 1
            if self._call_count % _SWEEP_INTERVAL == 0:
                self._sweep_locked(now)

            return allowed

    def _sweep_locked(self, now: float) -> None:
        cutoff = now - self._idle_ttl_seconds
        stale_keys = [key for key, seen in self._last_seen.items() if seen < cutoff]
        for key in stale_keys:
            del self._timestamps[key]
            del self._last_seen[key]
