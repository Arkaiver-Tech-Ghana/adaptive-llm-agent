import pytest

from adaptive_agent.entities.base import ColumnDef, ColumnType, TableDef
from adaptive_agent.entities.sqlite_repository import SqliteEntityRepository
from adaptive_agent.tools.base import UnknownToolError
from adaptive_agent.tools.entity_crud_provider import EntityCrudToolProvider

_NOTES_TABLE = TableDef(
    table_name="notes",
    display_name="Notes",
    columns=[ColumnDef(name="title", type=ColumnType.TEXT, required=True)],
)


def _provider(tmp_path) -> tuple[EntityCrudToolProvider, SqliteEntityRepository]:
    repo = SqliteEntityRepository(tmp_path / "business.sqlite3")
    repo.create_table(_NOTES_TABLE)
    return EntityCrudToolProvider(repo), repo


def test_create_then_list_round_trips(tmp_path):
    provider, _ = _provider(tmp_path)

    created = provider.call("create_notes", {"title": "First"})
    assert created["success"] is True
    assert created["title"] == "First"

    listed = provider.call("list_notes", {})
    assert [r["title"] for r in listed["rows"]] == ["First"]


def test_update_changes_only_the_given_fields(tmp_path):
    provider, repo = _provider(tmp_path)
    row = repo.upsert_row("notes", {"title": "Original"})

    updated = provider.call("update_notes", {"id": row["id"], "title": "Changed"})

    assert updated["success"] is True
    assert updated["title"] == "Changed"
    assert updated["id"] == row["id"]


def test_update_unknown_row_id_is_a_normal_failure_not_an_error(tmp_path):
    provider, _ = _provider(tmp_path)

    result = provider.call("update_notes", {"id": "ghost", "title": "x"})

    assert result["success"] is False


def test_delete_removes_the_row(tmp_path):
    provider, repo = _provider(tmp_path)
    row = repo.upsert_row("notes", {"title": "Gone soon"})

    result = provider.call("delete_notes", {"id": row["id"]})

    assert result["success"] is True
    assert repo.get_row("notes", row["id"]) is None


def test_unparseable_tool_name_raises_unknown_tool_error(tmp_path):
    provider, _ = _provider(tmp_path)
    with pytest.raises(UnknownToolError):
        provider.call("check_room_availability", {})


def test_verb_for_a_nonexistent_table_raises_unknown_tool_error(tmp_path):
    provider, _ = _provider(tmp_path)
    with pytest.raises(UnknownToolError):
        provider.call("list_ghost_table", {})


def test_verb_for_a_tool_linked_table_raises_unknown_tool_error(tmp_path):
    # tool_linked tables already have a hand-authored Tool — the generic
    # CRUD provider must not also answer for them.
    repo = SqliteEntityRepository(tmp_path / "business.sqlite3")
    repo.create_table(
        TableDef(
            table_name="menu_items",
            display_name="Menu",
            tool_linked="sqlite_menu",
            columns=[
                ColumnDef(name="name", type=ColumnType.TEXT, required=True),
                ColumnDef(name="category", type=ColumnType.TEXT, required=True),
                ColumnDef(name="price", type=ColumnType.NUMBER, required=True),
                ColumnDef(name="stock_quantity", type=ColumnType.NUMBER, required=True),
            ],
        )
    )
    provider = EntityCrudToolProvider(repo)

    with pytest.raises(UnknownToolError):
        provider.call("list_menu_items", {})
