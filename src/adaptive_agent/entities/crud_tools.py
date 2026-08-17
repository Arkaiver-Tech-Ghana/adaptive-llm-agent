"""Derives the 4 CRUD Tools (list/create/update/delete) a Custom Table gets
automatically the moment an owner creates it — the "generic CRUD tool" idea
ADR 0008 flagged as follow-up. Only a table with ``tool_linked: None``
qualifies: a ``tool_linked`` table (e.g. ``sqlite_menu``) already has a
hand-authored, purpose-built Tool wired into ``tools/registry.py``, and
generating a second, generic set of CRUD Tools for it would be redundant
and could let the LLM bypass that Tool's curated semantics.

Pure functions only — no I/O. ``entities_router.py`` calls these at
table-create/table-delete time and merges the result into the Business
Config's ``tools:`` list via ``business_config.writer``; ``EntityCrudToolProvider``
(tools/entity_crud_provider.py) parses the same name convention back apart
at call time. Both sides import ``crud_tool_names`` so the convention is
defined exactly once.
"""

from adaptive_agent.business_config.schema import ToolConfig
from adaptive_agent.entities.base import ColumnType, TableDef

_JSON_TYPE_BY_COLUMN_TYPE = {
    ColumnType.TEXT: "string",
    ColumnType.NUMBER: "number",
    ColumnType.BOOLEAN: "boolean",
}


def crud_tool_names(table_name: str) -> list[str]:
    """The 4 Tool names a Custom Table named ``table_name`` owns — shared by
    the generator below and ``EntityCrudToolProvider``'s dispatch, and by
    ``entities_router.py`` to know which Tool entries to drop when the
    table is deleted."""
    return [f"{verb}_{table_name}" for verb in ("list", "create", "update", "delete")]


def _column_properties(table_def: TableDef) -> dict[str, dict]:
    return {
        column.name: {
            "type": _JSON_TYPE_BY_COLUMN_TYPE[column.type],
            "description": f"The row's {column.name!r} value.",
        }
        for column in table_def.columns
    }


def derive_crud_tool_configs(table_def: TableDef) -> list[ToolConfig]:
    """The 4 auto-generated ToolConfigs for ``table_def``. Raises nothing —
    callers are expected to only call this for a ``tool_linked is None``
    table; that's a caller-side decision, not something this pure function
    re-validates."""
    properties = _column_properties(table_def)
    required = [c.name for c in table_def.columns if c.required]
    id_property = {"id": {"type": "string", "description": "The row's id."}}

    return [
        ToolConfig(
            name=f"list_{table_def.table_name}",
            description=f"List every row in the {table_def.display_name!r} table.",
            input_schema={"type": "object", "properties": {}},
            requires_confirmation=False,
        ),
        ToolConfig(
            name=f"create_{table_def.table_name}",
            description=f"Add a new row to the {table_def.display_name!r} table.",
            input_schema={
                "type": "object",
                "properties": properties,
                "required": required,
            },
            requires_confirmation=True,
        ),
        ToolConfig(
            name=f"update_{table_def.table_name}",
            description=(
                f"Update an existing row in the {table_def.display_name!r} table by id. "
                "Only the fields provided are changed; the rest keep their current value."
            ),
            input_schema={
                "type": "object",
                "properties": {**id_property, **properties},
                "required": ["id"],
            },
            requires_confirmation=True,
        ),
        ToolConfig(
            name=f"delete_{table_def.table_name}",
            description=f"Delete a row from the {table_def.display_name!r} table by id.",
            input_schema={"type": "object", "properties": id_property, "required": ["id"]},
            requires_confirmation=True,
        ),
    ]
