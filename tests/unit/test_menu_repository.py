from pathlib import Path

from adaptive_agent.menu.base import MenuItem
from adaptive_agent.menu.sqlite_repository import SqliteMenuRepository


def _store(tmp_path: Path) -> SqliteMenuRepository:
    return SqliteMenuRepository(tmp_path / "menu.sqlite3")


def test_get_item_is_none_for_unknown_name(tmp_path):
    repo = _store(tmp_path)
    assert repo.get_item("Veggie Burger") is None


def test_seed_then_get_item_round_trips(tmp_path):
    repo = _store(tmp_path)
    item = MenuItem(name="Veggie Burger", category="burgers", price=6.0, stock_quantity=10)
    repo.seed([item])
    assert repo.get_item("Veggie Burger") == item


def test_list_items_returns_every_seeded_item(tmp_path):
    repo = _store(tmp_path)
    items = [
        MenuItem(name="Veggie Burger", category="burgers", price=6.0, stock_quantity=10),
        MenuItem(name="Fries", category="sides", price=2.5, stock_quantity=20),
    ]
    repo.seed(items)
    assert {item.name for item in repo.list_items()} == {"Veggie Burger", "Fries"}


def test_seed_is_safe_to_rerun_and_overwrites_changed_fields(tmp_path):
    repo = _store(tmp_path)
    repo.seed([MenuItem(name="Fries", category="sides", price=2.5, stock_quantity=20)])
    repo.seed([MenuItem(name="Fries", category="sides", price=3.0, stock_quantity=5)])

    item = repo.get_item("Fries")
    assert item.price == 3.0
    assert item.stock_quantity == 5
    assert len(repo.list_items()) == 1


def test_persists_across_instances(tmp_path):
    db_path = tmp_path / "menu.sqlite3"
    item = MenuItem(name="Fries", category="sides", price=2.5, stock_quantity=20)
    SqliteMenuRepository(db_path).seed([item])

    second = SqliteMenuRepository(db_path)
    assert second.get_item("Fries") == item
