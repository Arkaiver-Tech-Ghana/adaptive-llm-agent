import pytest

from adaptive_agent.business_config.schema import StorageConfig
from adaptive_agent.entities.base import ColumnDef, ColumnType, TableDef
from adaptive_agent.entities.menu_repository_adapter import EntityBackedMenuRepository
from adaptive_agent.entities.sqlite_repository import SqliteEntityRepository
from adaptive_agent.menu.base import MenuItem
from adaptive_agent.tools.in_memory_provider import InMemoryToolProvider
from adaptive_agent.tools.kampuscrave_provider import KampusCraveToolProvider
from adaptive_agent.tools.registry import UnknownToolProviderError, build_tool_provider

_DEFAULT_STORAGE = StorageConfig()


def test_build_tool_provider_for_in_memory_type_returns_in_memory_provider(tmp_path):
    provider = build_tool_provider(
        "in_memory", _DEFAULT_STORAGE, tmp_path / "hotel.sqlite3"
    )
    assert isinstance(provider, InMemoryToolProvider)


def test_build_tool_provider_for_sqlite_menu_type_returns_kampuscrave_provider(tmp_path):
    provider = build_tool_provider(
        "sqlite_menu", _DEFAULT_STORAGE, tmp_path / "kampuscrave.sqlite3"
    )
    assert isinstance(provider, KampusCraveToolProvider)
    assert isinstance(provider.menu_repository, EntityBackedMenuRepository)


def test_build_tool_provider_for_sqlite_menu_creates_default_table_when_none_exists(tmp_path):
    db_path = tmp_path / "kampuscrave.sqlite3"

    provider = build_tool_provider("sqlite_menu", _DEFAULT_STORAGE, db_path)
    provider.menu_repository.seed(
        [MenuItem(name="Fries", category="sides", price=2.5, stock_quantity=20)]
    )
    result = provider.call("check_menu_item", {"item_name": "Fries"})
    assert result == {
        "found": True,
        "item_name": "Fries",
        "category": "sides",
        "price": 2.5,
        "stock_quantity": 20,
    }


def test_build_tool_provider_for_sqlite_menu_resolves_an_owner_customized_table(tmp_path):
    db_path = tmp_path / "kampuscrave.sqlite3"

    # An owner already built their own tool_linked table with a custom name
    # and an extra column beyond the required superset — the provider
    # should resolve to it instead of creating another default one.
    entity_repository = SqliteEntityRepository(db_path)
    entity_repository.create_table(
        TableDef(
            table_name="products",
            display_name="Products",
            tool_linked="sqlite_menu",
            columns=[
                ColumnDef(name="name", type=ColumnType.TEXT),
                ColumnDef(name="category", type=ColumnType.TEXT),
                ColumnDef(name="price", type=ColumnType.NUMBER),
                ColumnDef(name="stock_quantity", type=ColumnType.NUMBER),
                ColumnDef(name="supplier", type=ColumnType.TEXT),
            ],
        )
    )

    provider = build_tool_provider("sqlite_menu", _DEFAULT_STORAGE, db_path)
    assert provider.menu_repository._table_name == "products"

    provider.menu_repository.seed(
        [MenuItem(name="Fries", category="sides", price=2.5, stock_quantity=20)]
    )
    assert entity_repository.list_rows("products")[0]["supplier"] is None


def test_unknown_provider_type_raises_helpful_error(tmp_path):
    with pytest.raises(UnknownToolProviderError, match="unknown-type"):
        build_tool_provider(
            "unknown-type", _DEFAULT_STORAGE, tmp_path / "unknown.sqlite3"
        )
