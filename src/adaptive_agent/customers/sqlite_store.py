"""SQLite implementation of CustomerStore, wired generically for every
Business (infra like SqliteSessionStore, not a per-business axis).

No business_id column: the per-business SQLite file itself is already the
isolation boundary (docs/adr/0003), same as SqliteSessionStore.
"""

import sqlite3
import threading
import time
from collections.abc import Callable
from pathlib import Path


class SqliteCustomerStore:
    """Implements CustomerStore."""

    def __init__(self, db_path: Path, now_fn: Callable[[], float] = time.time) -> None:
        self._now_fn = now_fn
        self._lock = threading.Lock()

        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                customer_id TEXT PRIMARY KEY,
                first_seen REAL NOT NULL,
                last_seen REAL NOT NULL
            )
            """
        )
        self._conn.commit()

    def record_visit(self, customer_id: str) -> None:
        now = self._now_fn()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO customers (customer_id, first_seen, last_seen)
                VALUES (?, ?, ?)
                ON CONFLICT(customer_id) DO UPDATE SET
                    last_seen = excluded.last_seen
                """,
                (customer_id, now, now),
            )
            self._conn.commit()
