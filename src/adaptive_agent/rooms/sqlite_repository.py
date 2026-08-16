"""SQLite implementation of RoomRepository — structural mirror of
menu/sqlite_repository.py. The Admin CRUD routes are the only caller today;
wiring the hotel's chat-facing booking tool onto this repository (instead of
tools/in_memory_provider.py) is a separate change.

Table and column names are configurable the same way SqliteMenuRepository's
are, via a Business Config's ``storage.table``/``storage.columns``.
"""

import re
import sqlite3
import threading
from pathlib import Path

from adaptive_agent.rooms.base import Room

DEFAULT_TABLE = "rooms"
DEFAULT_COLUMNS = {
    "name": "name",
    "room_type": "room_type",
    "price_per_night": "price_per_night",
    "availability_count": "availability_count",
}
_REQUIRED_FIELDS = frozenset(DEFAULT_COLUMNS)

# Re-validated here (not just at Business Config load) since this class can
# be constructed directly — e.g. by scripts/tests — bypassing schema.py's
# pydantic validators. Table/column names are interpolated straight into
# SQL strings (sqlite3 can't bind identifiers with `?`), so this is the
# actual injection guard, not just a config-load nicety.
_SQL_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class InvalidRoomTableConfigError(Exception):
    """Raised when a ``table``/``columns`` override isn't usable: not a
    valid SQL identifier, or ``columns`` is missing/misnaming one of the
    fields this repository requires."""


def _validate_identifier(value: str) -> str:
    if not _SQL_IDENTIFIER_RE.match(value):
        raise InvalidRoomTableConfigError(f"Not a valid SQL identifier: {value!r}")
    return value


class SqliteRoomRepository:
    """Implements RoomRepository."""

    def __init__(
        self,
        db_path: Path,
        table: str = DEFAULT_TABLE,
        columns: dict[str, str] | None = None,
    ) -> None:
        columns = columns or DEFAULT_COLUMNS
        if set(columns) != _REQUIRED_FIELDS:
            raise InvalidRoomTableConfigError(
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
                {col["room_type"]} TEXT NOT NULL,
                {col["price_per_night"]} REAL NOT NULL,
                {col["availability_count"]} INTEGER NOT NULL
            )
            """
        )
        self._conn.commit()

    def get_room(self, name: str) -> Room | None:
        col = self._columns
        with self._lock:
            row = self._conn.execute(
                f"SELECT {col['name']}, {col['room_type']}, {col['price_per_night']}, "
                f"{col['availability_count']} FROM {self._table} WHERE {col['name']} = ?",
                (name,),
            ).fetchone()
        if row is None:
            return None
        return Room(
            name=row[0], room_type=row[1], price_per_night=row[2], availability_count=row[3]
        )

    def list_rooms(self) -> list[Room]:
        col = self._columns
        with self._lock:
            rows = self._conn.execute(
                f"SELECT {col['name']}, {col['room_type']}, {col['price_per_night']}, "
                f"{col['availability_count']} FROM {self._table}"
            ).fetchall()
        return [
            Room(name=row[0], room_type=row[1], price_per_night=row[2], availability_count=row[3])
            for row in rows
        ]

    def seed(self, rooms: list[Room]) -> None:
        col = self._columns
        # OR REPLACE, not OR IGNORE: re-running the seed script after
        # editing a price/availability number in it should apply the edit,
        # not silently no-op because the name already exists.
        with self._lock:
            self._conn.executemany(
                f"""
                INSERT OR REPLACE INTO {self._table}
                    ({col["name"]}, {col["room_type"]}, {col["price_per_night"]}, {col["availability_count"]})
                VALUES (?, ?, ?, ?)
                """,
                [
                    (room.name, room.room_type, room.price_per_night, room.availability_count)
                    for room in rooms
                ],
            )
            self._conn.commit()

    def delete_room(self, name: str) -> bool:
        col = self._columns
        with self._lock:
            cursor = self._conn.execute(
                f"DELETE FROM {self._table} WHERE {col['name']} = ?", (name,)
            )
            self._conn.commit()
        return cursor.rowcount > 0
