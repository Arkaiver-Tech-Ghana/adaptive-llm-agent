import pytest

from adaptive_agent.business_config.schema import StorageConfig
from adaptive_agent.menu.base import MenuItem
from adaptive_agent.menu.sqlite_repository import SqliteMenuRepository
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


def test_build_tool_provider_for_sqlite_menu_honors_custom_table_and_columns(tmp_path):
    storage_config = StorageConfig(
        table="products",
        columns={
            "name": "item_name",
            "category": "cat",
            "price": "unit_price",
            "stock_quantity": "qty",
        },
    )
    db_path = tmp_path / "kampuscrave.sqlite3"

    provider = build_tool_provider("sqlite_menu", storage_config, db_path)
    assert isinstance(provider, KampusCraveToolProvider)
    assert isinstance(provider.menu_repository, SqliteMenuRepository)

    # Prove it's really reading/writing the configured table, not the default.
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


def test_unknown_provider_type_raises_helpful_error(tmp_path):
    with pytest.raises(UnknownToolProviderError, match="unknown-type"):
        build_tool_provider(
            "unknown-type", _DEFAULT_STORAGE, tmp_path / "unknown.sqlite3"
        )
