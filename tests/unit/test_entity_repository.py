import pytest

from adaptive_agent.entities.base import ColumnDef, ColumnType, TableDef
from adaptive_agent.entities.sqlite_repository import (
    InvalidTableConfigError,
    InvalidToolLinkedTableError,
    SqliteEntityRepository,
    TableAlreadyExistsError,
    UnknownTableError,
)


def _repo(tmp_path) -> SqliteEntityRepository:
    return SqliteEntityRepository(tmp_path / "business.sqlite3")


def _notes_table(**overrides) -> TableDef:
    defaults = {
        "table_name": "notes",
        "display_name": "Notes",
        "columns": [
            ColumnDef(name="title", type=ColumnType.TEXT, required=True),
            ColumnDef(name="pinned", type=ColumnType.BOOLEAN),
            ColumnDef(name="rank", type=ColumnType.NUMBER),
        ],
    }
    defaults.update(overrides)
    return TableDef(**defaults)


def test_create_table_then_list_tables_round_trips(tmp_path):
    repo = _repo(tmp_path)
    repo.create_table(_notes_table())

    tables = repo.list_tables()
    assert len(tables) == 1
    assert tables[0].table_name == "notes"
    assert {c.name for c in tables[0].columns} == {"title", "pinned", "rank"}


def test_create_table_rejects_duplicate_name(tmp_path):
    repo = _repo(tmp_path)
    repo.create_table(_notes_table())
    with pytest.raises(TableAlreadyExistsError):
        repo.create_table(_notes_table())


def test_create_table_rejects_invalid_identifier(tmp_path):
    repo = _repo(tmp_path)
    with pytest.raises(InvalidTableConfigError):
        repo.create_table(_notes_table(table_name="not a valid name"))


def test_create_table_rejects_tool_linked_table_missing_required_columns(tmp_path):
    repo = _repo(tmp_path)
    with pytest.raises(InvalidToolLinkedTableError):
        repo.create_table(
            TableDef(
                table_name="menu_items",
                display_name="Menu Items",
                tool_linked="sqlite_menu",
                columns=[ColumnDef(name="name", type=ColumnType.TEXT)],
            )
        )


def test_create_table_rejects_second_table_linked_to_same_tool(tmp_path):
    repo = _repo(tmp_path)
    menu_columns = [
        ColumnDef(name="name", type=ColumnType.TEXT),
        ColumnDef(name="category", type=ColumnType.TEXT),
        ColumnDef(name="price", type=ColumnType.NUMBER),
        ColumnDef(name="stock_quantity", type=ColumnType.NUMBER),
    ]
    repo.create_table(
        TableDef(table_name="a", display_name="A", tool_linked="sqlite_menu", columns=menu_columns)
    )
    with pytest.raises(InvalidToolLinkedTableError):
        repo.create_table(
            TableDef(table_name="b", display_name="B", tool_linked="sqlite_menu", columns=menu_columns)
        )


def test_upsert_row_without_id_generates_one(tmp_path):
    repo = _repo(tmp_path)
    repo.create_table(_notes_table())

    stored = repo.upsert_row("notes", {"title": "First", "pinned": True, "rank": 1})
    assert stored["id"]
    assert stored["title"] == "First"
    assert stored["pinned"] is True
    assert stored["rank"] == 1


def test_upsert_row_with_id_overwrites_existing_row(tmp_path):
    repo = _repo(tmp_path)
    repo.create_table(_notes_table())
    created = repo.upsert_row("notes", {"title": "First", "pinned": False, "rank": 1})

    updated = repo.upsert_row("notes", {"id": created["id"], "title": "Updated", "pinned": True, "rank": 2})
    assert updated["id"] == created["id"]
    assert repo.list_rows("notes") == [updated]


def test_get_row_is_none_for_unknown_id(tmp_path):
    repo = _repo(tmp_path)
    repo.create_table(_notes_table())
    assert repo.get_row("notes", "nope") is None


def test_delete_row_removes_it_and_reports_whether_it_existed(tmp_path):
    repo = _repo(tmp_path)
    repo.create_table(_notes_table())
    created = repo.upsert_row("notes", {"title": "First", "pinned": False, "rank": 1})

    assert repo.delete_row("notes", created["id"]) is True
    assert repo.get_row("notes", created["id"]) is None
    assert repo.delete_row("notes", created["id"]) is False


def test_drop_table_removes_table_and_its_metadata(tmp_path):
    repo = _repo(tmp_path)
    repo.create_table(_notes_table())
    repo.upsert_row("notes", {"title": "First", "pinned": False, "rank": 1})

    repo.drop_table("notes")
    assert repo.list_tables() == []
    with pytest.raises(UnknownTableError):
        repo.list_rows("notes")


def test_operations_on_unknown_table_raise(tmp_path):
    repo = _repo(tmp_path)
    with pytest.raises(UnknownTableError):
        repo.list_rows("ghost")
    with pytest.raises(UnknownTableError):
        repo.upsert_row("ghost", {"title": "x"})
    with pytest.raises(UnknownTableError):
        repo.delete_row("ghost", "1")
    with pytest.raises(UnknownTableError):
        repo.drop_table("ghost")


def test_metadata_persists_across_instances(tmp_path):
    db_path = tmp_path / "business.sqlite3"
    SqliteEntityRepository(db_path).create_table(_notes_table())

    second = SqliteEntityRepository(db_path)
    assert [t.table_name for t in second.list_tables()] == ["notes"]
