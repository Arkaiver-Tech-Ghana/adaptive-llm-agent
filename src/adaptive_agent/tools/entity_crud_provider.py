"""Dispatches the auto-generated ``list_<table>``/``create_<table>``/
``update_<table>``/``delete_<table>`` Tools (entities/crud_tools.py) to an
owner's Custom Table via ``EntityRepository``. One instance covers every
Custom Table a Business has — it looks the table up by name out of
``list_tables()`` on each call rather than being constructed per-table, so
a table an owner adds after this provider is built still works.

Every Business gets one of these regardless of its ``tool_provider``
selection (tools/registry.py) — composed alongside that domain-specific
provider via CompositeToolProvider (tools/composite_provider.py) — since
Custom Tables are a per-Business-instance thing, not a provider-type
choice.
"""

from typing import Any

from adaptive_agent.entities.base import EntityRepository, TableDef
from adaptive_agent.tools.base import UnknownToolError

_VERBS = ("list", "create", "update", "delete")


def _parse_tool_name(name: str) -> tuple[str, str] | None:
    """Splits ``"<verb>_<table_name>"`` apart, or returns None if ``name``
    doesn't match the convention at all."""
    verb, sep, table_name = name.partition("_")
    if not sep or verb not in _VERBS or not table_name:
        return None
    return verb, table_name


class EntityCrudToolProvider:
    """Implements ToolProvider."""

    def __init__(self, entity_repository: EntityRepository) -> None:
        self._entity_repository = entity_repository

    def call(self, name: str, arguments: dict[str, Any]) -> Any:
        parsed = _parse_tool_name(name)
        if parsed is None:
            raise UnknownToolError(f"Unknown tool: {name!r}")
        verb, table_name = parsed

        table = self._find_table(table_name)
        # A forged/stale call naming a real verb but a table that doesn't
        # exist (or is tool_linked, so it never had these Tools generated)
        # is the same "unknown tool" situation as a bad name outright — the
        # Tool Rail already checked the name against business.yaml's tools
        # list before this ever runs, so this only fires on drift (e.g. the
        # table was deleted mid-conversation).
        if table is None or table.tool_linked is not None:
            raise UnknownToolError(f"Unknown tool: {name!r}")

        if verb == "list":
            return {"rows": self._entity_repository.list_rows(table_name)}
        if verb == "create":
            row = {k: v for k, v in arguments.items() if k != "id"}
            created = self._entity_repository.upsert_row(table_name, row)
            return {"success": True, **created}
        if verb == "update":
            return self._update(table_name, arguments)
        return self._delete(table_name, arguments)

    def _find_table(self, table_name: str) -> TableDef | None:
        return next(
            (t for t in self._entity_repository.list_tables() if t.table_name == table_name),
            None,
        )

    def _update(self, table_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        row_id = arguments["id"]
        existing = self._entity_repository.get_row(table_name, row_id)
        if existing is None:
            return {"success": False, "error": f"No such row: {row_id!r}"}
        patch = {k: v for k, v in arguments.items() if k != "id"}
        updated = self._entity_repository.upsert_row(table_name, {**existing, **patch, "id": row_id})
        return {"success": True, **updated}

    def _delete(self, table_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        row_id = arguments["id"]
        deleted = self._entity_repository.delete_row(table_name, row_id)
        if not deleted:
            return {"success": False, "error": f"No such row: {row_id!r}"}
        return {"success": True}
