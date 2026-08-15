"""SQLite implementation of MenuRepository — one of possibly several; the
Tool provider only ever depends on the Protocol (base.py).

Mirrors session/sqlite_store.py's exact connection pattern: one shared
connection, WAL mode, a threading.Lock around every read/write.
"""

import sqlite3
import threading
from pathlib import Path

from adaptive_agent.menu.base import MenuItem


class SqliteMenuRepository:
    """Implements MenuRepository."""

    def __init__(self, db_path: Path) -> None:
        self._lock = threading.Lock()

        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS menu_items (
                name TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                price REAL NOT NULL,
                stock_quantity INTEGER NOT NULL
            )
            """
        )
        self._conn.commit()

    def get_item(self, name: str) -> MenuItem | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT name, category, price, stock_quantity FROM menu_items WHERE name = ?",
                (name,),
            ).fetchone()
        if row is None:
            return None
        return MenuItem(name=row[0], category=row[1], price=row[2], stock_quantity=row[3])

    def list_items(self) -> list[MenuItem]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT name, category, price, stock_quantity FROM menu_items"
            ).fetchall()
        return [
            MenuItem(name=row[0], category=row[1], price=row[2], stock_quantity=row[3])
            for row in rows
        ]

    def seed(self, items: list[MenuItem]) -> None:
        # OR REPLACE, not OR IGNORE: re-running the seed script after
        # editing a price/stock number in it should apply the edit, not
        # silently no-op because the name already exists.
        with self._lock:
            self._conn.executemany(
                """
                INSERT OR REPLACE INTO menu_items (name, category, price, stock_quantity)
                VALUES (?, ?, ?, ?)
                """,
                [(item.name, item.category, item.price, item.stock_quantity) for item in items],
            )
            self._conn.commit()
