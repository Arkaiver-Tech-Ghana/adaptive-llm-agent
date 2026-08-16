"""Regression guard for the one live chat-facing demo path this migration
touches: KampusCrave's check_menu_item tool. Proves EntityBackedMenuRepository
gives tools/kampuscrave_provider.py the exact same MenuRepository behavior
SqliteMenuRepository used to, since that file itself is not being changed —
only what gets constructed and injected into it.
"""

from adaptive_agent.entities.menu_repository_adapter import EntityBackedMenuRepository
from adaptive_agent.entities.sqlite_repository import SqliteEntityRepository
from adaptive_agent.menu.base import MenuItem
from adaptive_agent.tools.kampuscrave_provider import KampusCraveToolProvider
from adaptive_agent.tools.registry import resolve_or_create_menu_table


def _provider(tmp_path) -> KampusCraveToolProvider:
    entity_repository = SqliteEntityRepository(tmp_path / "kampuscrave.sqlite3")
    table_name = resolve_or_create_menu_table(entity_repository)
    return KampusCraveToolProvider(EntityBackedMenuRepository(entity_repository, table_name))


def test_check_menu_item_found_matches_the_old_shape(tmp_path):
    provider = _provider(tmp_path)
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


def test_check_menu_item_not_found_matches_the_old_shape(tmp_path):
    provider = _provider(tmp_path)

    result = provider.call("check_menu_item", {"item_name": "Nonexistent"})
    assert result == {
        "found": False,
        "item_name": "Nonexistent",
        "reason": "No such menu item: 'Nonexistent'",
    }


def test_seed_is_idempotent_upsert_by_name(tmp_path):
    provider = _provider(tmp_path)
    provider.menu_repository.seed(
        [MenuItem(name="Fries", category="sides", price=2.5, stock_quantity=20)]
    )
    provider.menu_repository.seed(
        [MenuItem(name="Fries", category="sides", price=3.0, stock_quantity=15)]
    )

    assert len(provider.menu_repository.list_items()) == 1
    result = provider.call("check_menu_item", {"item_name": "Fries"})
    assert result["price"] == 3.0
    assert result["stock_quantity"] == 15


def test_delete_item_removes_it_from_the_chat_tool(tmp_path):
    provider = _provider(tmp_path)
    provider.menu_repository.seed(
        [MenuItem(name="Fries", category="sides", price=2.5, stock_quantity=20)]
    )

    assert provider.menu_repository.delete_item("Fries") is True
    result = provider.call("check_menu_item", {"item_name": "Fries"})
    assert result["found"] is False
