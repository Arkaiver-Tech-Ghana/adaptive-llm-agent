"""SQLite implementation of AdminStore — one shared platform-wide file
(``data/admin.sqlite3`` by default), not one per Business (ADR 0006).
Connection/locking pattern mirrors session/sqlite_store.py and
customers/sqlite_store.py exactly: one shared connection, WAL mode, a
threading.Lock around every read/write, no connection pool.
"""

import sqlite3
import threading
import time
from collections.abc import Callable
from pathlib import Path

from adaptive_agent.admin.base import AdminAuditLogEntry, AdminRole, AdminUser


class SqliteAdminStore:
    """Implements AdminStore."""

    def __init__(self, db_path: Path, now_fn: Callable[[], float] = time.time) -> None:
        self._now_fn = now_fn
        self._lock = threading.Lock()

        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_users (
                email TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                business_id TEXT
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_email TEXT NOT NULL,
                business_id TEXT,
                action TEXT NOT NULL,
                before TEXT,
                after TEXT,
                timestamp REAL NOT NULL
            )
            """
        )
        self._conn.commit()

    def get_user_by_email(self, email: str) -> AdminUser | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT email, password_hash, role, business_id FROM admin_users WHERE email = ?",
                (email,),
            ).fetchone()
        if row is None:
            return None
        return AdminUser(
            email=row[0], password_hash=row[1], role=AdminRole(row[2]), business_id=row[3]
        )

    def upsert_user(self, user: AdminUser) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO admin_users (email, password_hash, role, business_id)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    password_hash = excluded.password_hash,
                    role = excluded.role,
                    business_id = excluded.business_id
                """,
                (user.email, user.password_hash, user.role.value, user.business_id),
            )
            self._conn.commit()

    def list_users_for_business(self, business_id: str) -> list[AdminUser]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT email, password_hash, role, business_id FROM admin_users "
                "WHERE business_id = ?",
                (business_id,),
            ).fetchall()
        return [
            AdminUser(email=row[0], password_hash=row[1], role=AdminRole(row[2]), business_id=row[3])
            for row in rows
        ]

    def append_audit_log(self, entry: AdminAuditLogEntry) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO admin_audit_log
                    (actor_email, business_id, action, before, after, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.actor_email,
                    entry.business_id,
                    entry.action,
                    entry.before,
                    entry.after,
                    entry.timestamp,
                ),
            )
            self._conn.commit()

    def list_audit_log(self, business_id: str | None) -> list[AdminAuditLogEntry]:
        with self._lock:
            if business_id is None:
                rows = self._conn.execute(
                    "SELECT id, actor_email, business_id, action, before, after, timestamp "
                    "FROM admin_audit_log ORDER BY id"
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT id, actor_email, business_id, action, before, after, timestamp "
                    "FROM admin_audit_log WHERE business_id = ? ORDER BY id",
                    (business_id,),
                ).fetchall()
        return [
            AdminAuditLogEntry(
                id=row[0],
                actor_email=row[1],
                business_id=row[2],
                action=row[3],
                before=row[4],
                after=row[5],
                timestamp=row[6],
            )
            for row in rows
        ]
