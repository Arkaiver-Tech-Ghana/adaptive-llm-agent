"""Message-id dedupe: WhatsApp retries a delivery under the same message
id, so keying on id alone (globally unique) is enough to catch a retry.

TTL (not LRU-by-count) because correctness here is time-based: a retried
delivery must be caught however long Meta's retry window runs. Eviction
happens lazily from the front of the dict on every call — Python dicts
preserve insertion order, and a re-seen id is never re-inserted (it's
already a duplicate), so the front of the dict is always the oldest
surviving entry. O(1) amortized, no background thread.
"""

import threading
import time
from collections.abc import Callable

_DEFAULT_TTL_SECONDS = 86400  # 24h


class InMemoryDedupeStore:
    def __init__(
        self,
        ttl_seconds: float = _DEFAULT_TTL_SECONDS,
        now_fn: Callable[[], float] = time.time,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._now_fn = now_fn
        self._seen: dict[str, float] = {}
        self._lock = threading.Lock()

    def is_duplicate(self, message_id: str) -> bool:
        now = self._now_fn()
        with self._lock:
            self._evict_expired_locked(now)
            if message_id in self._seen:
                return True
            self._seen[message_id] = now
            return False

    def _evict_expired_locked(self, now: float) -> None:
        cutoff = now - self._ttl_seconds
        while self._seen:
            oldest_id = next(iter(self._seen))
            if self._seen[oldest_id] >= cutoff:
                break
            del self._seen[oldest_id]
