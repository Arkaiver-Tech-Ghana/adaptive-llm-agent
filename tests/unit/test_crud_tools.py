from adaptive_agent.entities.base import ColumnDef, ColumnType, TableDef
from adaptive_agent.entities.crud_tools import crud_tool_names, derive_crud_tool_configs

_NOTES_TABLE = TableDef(
    table_name="notes",
    display_name="Notes",
    columns=[
        ColumnDef(name="title", type=ColumnType.TEXT, required=True),
        ColumnDef(name="pinned", type=ColumnType.BOOLEAN),
    ],
)


def test_crud_tool_names_follows_verb_underscore_table_convention():
    assert crud_tool_names("notes") == [
        "list_notes",
        "create_notes",
        "update_notes",
        "delete_notes",
    ]


def test_derive_crud_tool_configs_generates_one_tool_per_verb():
    tools = derive_crud_tool_configs(_NOTES_TABLE)
    assert [t.name for t in tools] == crud_tool_names("notes")


def test_list_tool_takes_no_arguments():
    tools = derive_crud_tool_configs(_NOTES_TABLE)
    list_tool = next(t for t in tools if t.name == "list_notes")
    assert list_tool.input_schema["properties"] == {}
    assert list_tool.requires_confirmation is False


def test_create_tool_schema_reflects_columns_and_required_flags():
    tools = derive_crud_tool_configs(_NOTES_TABLE)
    create_tool = next(t for t in tools if t.name == "create_notes")
    assert create_tool.input_schema["properties"]["title"]["type"] == "string"
    assert create_tool.input_schema["properties"]["pinned"]["type"] == "boolean"
    assert create_tool.input_schema["required"] == ["title"]
    assert create_tool.requires_confirmation is True


def test_update_and_delete_tools_require_an_id_and_confirmation():
    tools = derive_crud_tool_configs(_NOTES_TABLE)
    update_tool = next(t for t in tools if t.name == "update_notes")
    delete_tool = next(t for t in tools if t.name == "delete_notes")

    assert "id" in update_tool.input_schema["properties"]
    assert update_tool.input_schema["required"] == ["id"]
    assert update_tool.requires_confirmation is True

    assert set(delete_tool.input_schema["properties"]) == {"id"}
    assert delete_tool.requires_confirmation is True
