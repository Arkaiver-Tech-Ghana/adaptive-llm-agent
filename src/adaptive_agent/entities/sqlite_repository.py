"""SQLite implementation of EntityRepository (ADR 0008). Owns a metadata
table, ``__qantonic_tables__``, per Business SQLite file alongside every
owner-created table it describes — this is how ``list_tables`` recovers
column names/types/``tool_linked`` without a separate config file. Mirrors
session/sqlite_store.py's connection pattern: one shared connection, WAL
mode, a threading.Lock around every read/write.

Table/column names come from the owner (via the admin UI) rather than a
developer-written literal, so every identifier is re-validated here even
though ``TableDef``'s caller may already have validated it once — this is
the actual injection guard, not just a nicety (see sql_identifiers.py).
Row/cell values always stay parameter-bound.
"""

import json
import sqlite3
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path

from adaptive_agent.entities.base import ColumnDef, ColumnType, IdType, TableDef
from adaptive_agent.sql_identifiers import validate_identifier

_SQL_TYPE_BY_COLUMN_TYPE = {
    ColumnType.TEXT: "TEXT",
    ColumnType.NUMBER: "REAL",
    ColumnType.BOOLEAN: "INTEGER",
}

# A table backing a chat-facing Tool must carry at least these columns
# (name -> type) — enforced at create_table() time, generalizing what
# SqliteMenuRepository/SqliteRoomRepository used to check in __init__.
# Extra owner-added columns beyond this set are fine (a superset, not an
# exact match).
_TOOL_LINKED_REQUIRED_COLUMNS: dict[str, dict[str, ColumnType]] = {
    "sqlite_menu": {
        "name": ColumnType.TEXT,
        "category": ColumnType.TEXT,
        "price": ColumnType.NUMBER,
        "stock_quantity": ColumnType.NUMBER,
    },
}


class InvalidTableConfigError(Exception):
    """Not a valid SQL identifier."""


class TableAlreadyExistsError(Exception):
    pass


class UnknownTableError(Exception):
    pass


class UnknownColumnError(Exception):
    pass


class ColumnAlreadyExistsError(Exception):
    pass


class InvalidToolLinkedTableError(Exception):
    """Raised when a TableDef claims a ``tool_linked`` type but doesn't
    carry the columns/types that type requires, or another table is
    already linked to the same type."""


class SqliteEntityRepository:
    """Implements EntityRepository."""

    def __init__(self, db_path: Path, now_fn: Callable[[], float] = time.time) -> None:
        self._now_fn = now_fn
        self._lock = threading.Lock()

        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS __qantonic_tables__ (
                table_name TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                columns_json TEXT NOT NULL,
                id_type TEXT NOT NULL DEFAULT 'uuid',
                tool_linked TEXT,
                created_at REAL NOT NULL
            )
            """
        )
        self._conn.commit()

    def list_tables(self) -> list[TableDef]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT table_name, display_name, columns_json, id_type, tool_linked "
                "FROM __qantonic_tables__ ORDER BY table_name"
            ).fetchall()
        return [self._table_def_from_row(row) for row in rows]

    def create_table(self, table_def: TableDef) -> None:
        table_name = validate_identifier(table_def.table_name, InvalidTableConfigError)
        columns = [
            ColumnDef(name=validate_identifier(c.name, InvalidTableConfigError), type=c.type, required=c.required)
            for c in table_def.columns
        ]
        if any(c.name == "id" for c in columns):
            raise InvalidTableConfigError("'id' is a reserved column name (auto-generated primary key)")

        if table_def.tool_linked is not None:
            self._check_tool_linked_requirements(table_def.tool_linked, columns)
            existing = next(
                (t for t in self.list_tables() if t.tool_linked == table_def.tool_linked), None
            )
            if existing is not None:
                raise InvalidToolLinkedTableError(
                    f"Business already has a table linked to {table_def.tool_linked!r}: "
                    f"{existing.table_name!r}"
                )

        with self._lock:
            existing_row = self._conn.execute(
                "SELECT 1 FROM __qantonic_tables__ WHERE table_name = ?", (table_name,)
            ).fetchone()
            if existing_row is not None:
                raise TableAlreadyExistsError(f"Table already exists: {table_name!r}")

            column_sql = ", ".join(
                f"{c.name} {_SQL_TYPE_BY_COLUMN_TYPE[c.type]}"
                f"{' NOT NULL' if c.required else ''}"
                for c in columns
            )
            id_column_sql = (
                "id INTEGER PRIMARY KEY AUTOINCREMENT"
                if table_def.id_type == IdType.AUTO_INCREMENT
                else "id TEXT PRIMARY KEY"
            )
            self._conn.execute(
                f"CREATE TABLE {table_name} ({id_column_sql}{', ' + column_sql if column_sql else ''})"
            )
            self._conn.execute(
                """
                INSERT INTO __qantonic_tables__
                    (table_name, display_name, columns_json, id_type, tool_linked, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    table_name,
                    table_def.display_name,
                    json.dumps([c.model_dump(mode="json") for c in columns]),
                    table_def.id_type.value,
                    table_def.tool_linked,
                    self._now_fn(),
                ),
            )
            self._conn.commit()

    def drop_table(self, table_name: str) -> None:
        table_def = self._require_table(table_name)
        with self._lock:
            self._conn.execute(f"DROP TABLE IF EXISTS {table_def.table_name}")
            self._conn.execute(
                "DELETE FROM __qantonic_tables__ WHERE table_name = ?", (table_def.table_name,)
            )
            self._conn.commit()

    def add_column(self, table_name: str, column: ColumnDef) -> TableDef:
        table_def = self._require_table(table_name)
        column_name = validate_identifier(column.name, InvalidTableConfigError)
        if column_name == "id" or any(c.name == column_name for c in table_def.columns):
            raise ColumnAlreadyExistsError(f"Column already exists: {column_name!r}")
        column = ColumnDef(name=column_name, type=column.type, required=column.required)

        with self._lock:
            # No NOT NULL here even if `required` is set: SQLite only allows
            # ALTER TABLE ADD COLUMN with a NOT NULL constraint when it also
            # carries a non-NULL DEFAULT, which nothing here collects — every
            # existing row would need a starting value. `required` still
            # round-trips through metadata for the caller's own validation.
            self._conn.execute(
                f"ALTER TABLE {table_def.table_name} ADD COLUMN {column.name} "
                f"{_SQL_TYPE_BY_COLUMN_TYPE[column.type]}"
            )
            updated_columns = [*table_def.columns, column]
            self._write_columns_metadata(table_name, updated_columns)
            self._conn.commit()
        return self._require_table(table_name)

    def rename_column(self, table_name: str, column_name: str, new_name: str) -> TableDef:
        table_def = self._require_table(table_name)
        new_name = validate_identifier(new_name, InvalidTableConfigError)
        existing = next((c for c in table_def.columns if c.name == column_name), None)
        if existing is None:
            raise UnknownColumnError(f"No such column: {column_name!r}")
        if new_name != column_name and any(c.name == new_name for c in table_def.columns):
            raise ColumnAlreadyExistsError(f"Column already exists: {new_name!r}")
        self._require_column_not_tool_linked(table_def, column_name, action="rename")

        with self._lock:
            self._conn.execute(
                f"ALTER TABLE {table_def.table_name} RENAME COLUMN {column_name} TO {new_name}"
            )
            updated_columns = [
                ColumnDef(name=new_name, type=c.type, required=c.required) if c.name == column_name else c
                for c in table_def.columns
            ]
            self._write_columns_metadata(table_name, updated_columns)
            self._conn.commit()
        return self._require_table(table_name)

    def drop_column(self, table_name: str, column_name: str) -> TableDef:
        table_def = self._require_table(table_name)
        if not any(c.name == column_name for c in table_def.columns):
            raise UnknownColumnError(f"No such column: {column_name!r}")
        self._require_column_not_tool_linked(table_def, column_name, action="remove")

        with self._lock:
            self._conn.execute(f"ALTER TABLE {table_def.table_name} DROP COLUMN {column_name}")
            updated_columns = [c for c in table_def.columns if c.name != column_name]
            self._write_columns_metadata(table_name, updated_columns)
            self._conn.commit()
        return self._require_table(table_name)

    def list_rows(self, table_name: str) -> list[dict]:
        table_def = self._require_table(table_name)
        column_names = ["id", *(c.name for c in table_def.columns)]
        with self._lock:
            rows = self._conn.execute(
                f"SELECT {', '.join(column_names)} FROM {table_def.table_name}"
            ).fetchall()
        return [self._row_to_dict(table_def, column_names, row) for row in rows]

    def get_row(self, table_name: str, row_id: str) -> dict | None:
        table_def = self._require_table(table_name)
        column_names = ["id", *(c.name for c in table_def.columns)]
        with self._lock:
            row = self._conn.execute(
                f"SELECT {', '.join(column_names)} FROM {table_def.table_name} WHERE id = ?",
                (row_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_dict(table_def, column_names, row)

    def upsert_row(self, table_name: str, row: dict) -> dict:
        table_def = self._require_table(table_name)
        column_names = [c.name for c in table_def.columns]
        values = [self._to_sql_value(c, row.get(c.name)) for c in table_def.columns]
        provided_id = row.get("id")

        with self._lock:
            if provided_id is None and table_def.id_type == IdType.AUTO_INCREMENT:
                # Omit `id` entirely so SQLite assigns the next AUTOINCREMENT
                # value — binding NULL would work too, but omitting it keeps
                # this branch's INSERT shape parallel to the explicit-id one.
                cursor = self._conn.execute(
                    f"""
                    INSERT INTO {table_def.table_name} ({", ".join(column_names)})
                    VALUES ({", ".join("?" for _ in column_names)})
                    """,
                    values,
                )
                row_id = cursor.lastrowid
            else:
                row_id = provided_id or uuid.uuid4().hex
                self._conn.execute(
                    f"""
                    INSERT OR REPLACE INTO {table_def.table_name}
                        (id, {", ".join(column_names)})
                    VALUES (?, {", ".join("?" for _ in column_names)})
                    """,
                    (row_id, *values),
                )
            self._conn.commit()

        stored = self.get_row(table_name, row_id)
        assert stored is not None
        return stored

    def delete_row(self, table_name: str, row_id: str) -> bool:
        table_def = self._require_table(table_name)
        with self._lock:
            cursor = self._conn.execute(
                f"DELETE FROM {table_def.table_name} WHERE id = ?", (row_id,)
            )
            self._conn.commit()
        return cursor.rowcount > 0

    def _require_table(self, table_name: str) -> TableDef:
        with self._lock:
            row = self._conn.execute(
                "SELECT table_name, display_name, columns_json, id_type, tool_linked "
                "FROM __qantonic_tables__ WHERE table_name = ?",
                (table_name,),
            ).fetchone()
        if row is None:
            raise UnknownTableError(f"No such table: {table_name!r}")
        return self._table_def_from_row(row)

    def _write_columns_metadata(self, table_name: str, columns: list[ColumnDef]) -> None:
        """Caller holds ``self._lock`` already — this only ever runs as
        part of a larger transaction alongside the ``ALTER TABLE`` it
        describes, never standalone."""
        self._conn.execute(
            "UPDATE __qantonic_tables__ SET columns_json = ? WHERE table_name = ?",
            (json.dumps([c.model_dump(mode="json") for c in columns]), table_name),
        )

    @staticmethod
    def _require_column_not_tool_linked(table_def: TableDef, column_name: str, action: str) -> None:
        if table_def.tool_linked is None:
            return
        required = _TOOL_LINKED_REQUIRED_COLUMNS.get(table_def.tool_linked, {})
        if column_name in required:
            raise InvalidToolLinkedTableError(
                f"Can't {action} {column_name!r}: required by tool_linked={table_def.tool_linked!r}"
            )

    @staticmethod
    def _check_tool_linked_requirements(tool_linked: str, columns: list[ColumnDef]) -> None:
        required = _TOOL_LINKED_REQUIRED_COLUMNS.get(tool_linked)
        if required is None:
            return
        provided = {c.name: c.type for c in columns}
        missing = {
            name: col_type
            for name, col_type in required.items()
            if provided.get(name) != col_type
        }
        if missing:
            raise InvalidToolLinkedTableError(
                f"Table linked to {tool_linked!r} is missing required columns: "
                f"{ {k: v.value for k, v in missing.items()} }"
            )

    @staticmethod
    def _table_def_from_row(row: tuple) -> TableDef:
        table_name, display_name, columns_json, id_type, tool_linked = row
        columns = [ColumnDef(**c) for c in json.loads(columns_json)]
        return TableDef(
            table_name=table_name,
            display_name=display_name,
            columns=columns,
            id_type=IdType(id_type),
            tool_linked=tool_linked,
        )

    @staticmethod
    def _to_sql_value(column: ColumnDef, value):
        if value is None:
            return None
        if column.type is ColumnType.BOOLEAN:
            return 1 if value else 0
        return value

    @staticmethod
    def _row_to_dict(table_def: TableDef, column_names: list[str], row: tuple) -> dict:
        columns_by_name = {c.name: c for c in table_def.columns}
        result = {}
        for name, value in zip(column_names, row, strict=True):
            column = columns_by_name.get(name)
            if column is not None and column.type is ColumnType.BOOLEAN and value is not None:
                value = bool(value)
            result[name] = value
        return result
