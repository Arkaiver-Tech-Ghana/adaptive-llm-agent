"""The v1 SessionStore, replacing InMemorySessionStore. Same Protocol
(session/base.py), one change: durability across process restarts — a
real VPS deployment will hit those (deploys, crashes, reboots), and
in-memory history/pending Confirmation Requests don't survive them.

One SQLite file per Business, WAL mode, one shared connection guarded by
a threading.Lock (matches the Lock-per-shared-state pattern used by
RateLimiter/InMemoryDedupeStore in interface_layer/) — no connection pool
needed at this project's scale.
"""

import json
import sqlite3
import threading
import time
from collections.abc import Callable
from pathlib import Path

from adaptive_agent.session.base import ConfirmationRequest

_SWEEP_INTERVAL = 500


class SqliteSessionStore:
    """Implements SessionStore."""

    def __init__(
        self,
        db_path: Path,
        idle_ttl_seconds: float = 7 * 86400,
        now_fn: Callable[[], float] = time.time,
    ) -> None:
        self._idle_ttl_seconds = idle_ttl_seconds
        self._now_fn = now_fn
        self._lock = threading.Lock()
        self._write_count = 0

        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_key TEXT PRIMARY KEY,
                history_json TEXT NOT NULL DEFAULT '[]',
                pending_confirmation_json TEXT,
                last_active REAL NOT NULL
            )
            """
        )
        self._conn.commit()

    def get_history(self, session_key: str) -> list[dict[str, str]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT history_json FROM sessions WHERE session_key = ?", (session_key,)
            ).fetchone()
        if row is None:
            return []
        return json.loads(row[0])

    def append(self, session_key: str, role: str, content: str) -> None:
        with self._lock:
            history, pending_json = self._get_row_locked(session_key)
            history.append({"role": role, "content": content})
            self._upsert_locked(session_key, json.dumps(history), pending_json)
            self._maybe_sweep_locked()

    def get_pending_confirmation(self, session_key: str) -> ConfirmationRequest | None:
        with self._lock:
            _, pending_json = self._get_row_locked(session_key)
        if pending_json is None:
            return None
        return ConfirmationRequest.model_validate_json(pending_json)

    def set_pending_confirmation(
        self, session_key: str, request: ConfirmationRequest | None
    ) -> None:
        with self._lock:
            history, _ = self._get_row_locked(session_key)
            pending_json = request.model_dump_json() if request is not None else None
            self._upsert_locked(session_key, json.dumps(history), pending_json)
            self._maybe_sweep_locked()

    def _get_row_locked(self, session_key: str) -> tuple[list[dict[str, str]], str | None]:
        row = self._conn.execute(
            "SELECT history_json, pending_confirmation_json FROM sessions WHERE session_key = ?",
            (session_key,),
        ).fetchone()
        if row is None:
            return [], None
        return json.loads(row[0]), row[1]

    def _upsert_locked(
        self, session_key: str, history_json: str, pending_confirmation_json: str | None
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO sessions (session_key, history_json, pending_confirmation_json, last_active)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(session_key) DO UPDATE SET
                history_json = excluded.history_json,
                pending_confirmation_json = excluded.pending_confirmation_json,
                last_active = excluded.last_active
            """,
            (session_key, history_json, pending_confirmation_json, self._now_fn()),
        )
        self._conn.commit()

    def _maybe_sweep_locked(self) -> None:
        self._write_count += 1
        if self._write_count % _SWEEP_INTERVAL != 0:
            return
        cutoff = self._now_fn() - self._idle_ttl_seconds
        self._conn.execute("DELETE FROM sessions WHERE last_active < ?", (cutoff,))
        self._conn.commit()
