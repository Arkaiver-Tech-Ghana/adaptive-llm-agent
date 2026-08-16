"""The storage-agnostic contract for a Business's owner-defined custom
tables (ADR 0008) — replaces the fixed ``Room``/``MenuItem`` schemas with a
generic table/column/row model a Business owner defines themselves through
the admin UI, instead of a developer adding a new repository class per
Business.

``EntityRepository`` is a Protocol, not just the SQLite implementation
below it, so a future backend (e.g. an external Supabase/Prisma-managed
table, schema fixed externally, CRUD-only) can implement the same contract
without ``entities_router.py`` or any ``tool_linked`` adapter changing —
see ADR 0008's "Future extensibility" note. Not built now, just not
foreclosed.
"""

from enum import Enum
from typing import Protocol

from pydantic import BaseModel


class ColumnType(str, Enum):
    """Deliberately minimal — text/number/boolean only. This is the seam a
    future AI-assisted table builder calls into; it doesn't need to grow
    ahead of an actual owner-facing use case."""

    TEXT = "text"
    NUMBER = "number"
    BOOLEAN = "boolean"


class IdType(str, Enum):
    """How a table's ``id`` primary key is generated. Chosen once at
    ``create_table`` time — switching it after rows exist isn't supported
    (would mean rewriting every existing id), so this is absent from the
    alter-columns surface on purpose."""

    UUID = "uuid"
    AUTO_INCREMENT = "auto_increment"


class ColumnDef(BaseModel):
    name: str
    type: ColumnType
    required: bool = False


class TableDef(BaseModel):
    table_name: str
    display_name: str
    columns: list[ColumnDef]
    # Defaults to the original behavior (an app-generated uuid4 hex) so
    # every TableDef written before this field existed keeps working
    # unchanged.
    id_type: IdType = IdType.UUID
    # Set when this table backs a chat-facing Tool (e.g. "sqlite_menu") —
    # tools/registry.py resolves a Business's tool provider by scanning for
    # the table with this value, instead of a hardcoded table name. None
    # for an owner's own custom tables with no Tool behind them.
    tool_linked: str | None = None


class EntityRepository(Protocol):
    def list_tables(self) -> list[TableDef]: ...
    def create_table(self, table_def: TableDef) -> None: ...
    def drop_table(self, table_name: str) -> None: ...
    def list_rows(self, table_name: str) -> list[dict]: ...
    def get_row(self, table_name: str, row_id: str) -> dict | None: ...
    # Upserts by ``row["id"]`` if present, otherwise generates one and
    # creates a new row. Returns the stored row (with its id).
    def upsert_row(self, table_name: str, row: dict) -> dict: ...
    def delete_row(self, table_name: str, row_id: str) -> bool: ...
