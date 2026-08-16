"""One-time (safe-to-rerun) seed script for KampusCrave's live menu table.

Only supplies data — the insert mechanics stay encapsulated in
EntityBackedMenuRepository.seed()/SqliteEntityRepository, so this script
never writes raw SQL. Mirrors
businesses/kampuscrave/context/menu.md's current items; the context doc
stays the source for general browsing/categories, this table becomes the
authoritative source for a specific item's price/stock.
"""

import os
from pathlib import Path

from adaptive_agent.entities.menu_repository_adapter import EntityBackedMenuRepository
from adaptive_agent.entities.sqlite_repository import SqliteEntityRepository
from adaptive_agent.menu.base import MenuItem
from adaptive_agent.tools.registry import resolve_or_create_menu_table

MENU_ITEMS = [
    MenuItem(name="Classic Beef Burger", category="burgers", price=6.50, stock_quantity=25),
    MenuItem(name="Veggie Burger", category="burgers", price=6.00, stock_quantity=20),
    MenuItem(name="Double Cheese Burger", category="burgers", price=8.00, stock_quantity=15),
    MenuItem(name="Fries", category="sides", price=2.50, stock_quantity=40),
    MenuItem(name="Sweet Potato Fries", category="sides", price=3.00, stock_quantity=30),
    MenuItem(name="Onion Rings", category="sides", price=3.50, stock_quantity=30),
    MenuItem(name="Fountain Soda", category="drinks", price=1.75, stock_quantity=50),
    MenuItem(name="Bottled Water", category="drinks", price=1.50, stock_quantity=50),
    MenuItem(name="Iced Tea", category="drinks", price=2.00, stock_quantity=40),
    MenuItem(
        name="Burger + Fries + Drink combo", category="combos", price=9.50, stock_quantity=20
    ),
]


def main() -> None:
    session_db_dir = Path(os.environ.get("SESSION_DB_DIR", "data"))
    db_path = session_db_dir / "kampuscrave.sqlite3"
    entity_repository = SqliteEntityRepository(db_path)
    table_name = resolve_or_create_menu_table(entity_repository)
    repository = EntityBackedMenuRepository(entity_repository, table_name)
    repository.seed(MENU_ITEMS)
    print(f"Seeded {len(MENU_ITEMS)} menu items into {db_path}")


if __name__ == "__main__":
    main()
