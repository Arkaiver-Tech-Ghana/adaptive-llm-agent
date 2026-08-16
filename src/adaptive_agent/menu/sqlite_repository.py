"""SQLite implementation of MenuRepository — one of possibly several; the
Tool provider only ever depends on the Protocol (base.py).

Table and column names are configurable (defaulting to the names below)
so a Business whose menu table doesn't match those defaults points this
repository at its own schema via Business Config's ``storage.table`` /
``storage.columns`` — see business_config/schema.py — instead of a code
change here.

Mirrors session/sqlite_store.py's exact connection pattern: one shared
connection, WAL mode, a threading.Lock around every read/write.
"""

import re
import sqlite3
import threading
from pathlib import Path

from adaptive_agent.menu.base import MenuItem

DEFAULT_TABLE = "menu_items"
DEFAULT_COLUMNS = {
    "name": "name",
    "category": "category",
    "price": "price",
    "stock_quantity": "stock_quantity",
}
_REQUIRED_FIELDS = frozenset(DEFAULT_COLUMNS)

# Re-validated here (not just at Business Config load) since this class can
# be constructed directly — e.g. by scripts/tests — bypassing schema.py's
# pydantic validators. Table/column names are interpolated straight into
# SQL strings below (sqlite3 can't bind identifiers with `?`), so this is
# the actual injection guard, not just a config-load nicety.
_SQL_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class InvalidMenuTableConfigError(Exception):
    """Raised when a ``table``/``columns`` override isn't usable: not a
    valid SQL identifier, or ``columns`` is missing/misnaming one of the
    fields this repository requires."""


def _validate_identifier(value: str) -> str:
    if not _SQL_IDENTIFIER_RE.match(value):
        raise InvalidMenuTableConfigError(f"Not a valid SQL identifier: {value!r}")
    return value


class SqliteMenuRepository:
    """Implements MenuRepository."""

    def __init__(
        self,
        db_path: Path,
        table: str = DEFAULT_TABLE,
        columns: dict[str, str] | None = None,
    ) -> None:
        columns = columns or DEFAULT_COLUMNS
        if set(columns) != _REQUIRED_FIELDS:
            raise InvalidMenuTableConfigError(
                f"columns must map exactly {sorted(_REQUIRED_FIELDS)}, got {sorted(columns)}"
            )
        self._table = _validate_identifier(table)
        self._columns = {
            field: _validate_identifier(column) for field, column in columns.items()
        }
        col = self._columns

        self._lock = threading.Lock()

        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self._table} (
                {col["name"]} TEXT PRIMARY KEY,
                {col["category"]} TEXT NOT NULL,
                {col["price"]} REAL NOT NULL,
                {col["stock_quantity"]} INTEGER NOT NULL
            )
            """
        )
        self._conn.commit()

    def get_item(self, name: str) -> MenuItem | None:
        col = self._columns
        with self._lock:
            row = self._conn.execute(
                f"SELECT {col['name']}, {col['category']}, {col['price']}, {col['stock_quantity']} "
                f"FROM {self._table} WHERE {col['name']} = ?",
                (name,),
            ).fetchone()
        if row is None:
            return None
        return MenuItem(
            name=row[0], category=row[1], price=row[2], stock_quantity=row[3]
        )

    def list_items(self) -> list[MenuItem]:
        col = self._columns
        with self._lock:
            rows = self._conn.execute(
                f"SELECT {col['name']}, {col['category']}, {col['price']}, {col['stock_quantity']} "
                f"FROM {self._table}"
            ).fetchall()
        return [
            MenuItem(name=row[0], category=row[1], price=row[2], stock_quantity=row[3])
            for row in rows
        ]

    def seed(self, items: list[MenuItem]) -> None:
        col = self._columns
        # OR REPLACE, not OR IGNORE: re-running the seed script after
        # editing a price/stock number in it should apply the edit, not
        # silently no-op because the name already exists.
        with self._lock:
            self._conn.executemany(
                f"""
                INSERT OR REPLACE INTO {self._table}
                    ({col["name"]}, {col["category"]}, {col["price"]}, {col["stock_quantity"]})
                VALUES (?, ?, ?, ?)
                """,
                [
                    (item.name, item.category, item.price, item.stock_quantity)
                    for item in items
                ],
            )
            self._conn.commit()
