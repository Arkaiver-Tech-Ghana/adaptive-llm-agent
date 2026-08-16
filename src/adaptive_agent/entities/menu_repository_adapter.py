"""Implements the existing ``MenuRepository`` Protocol (menu/base.py) by
delegating to a ``tool_linked="sqlite_menu"`` table in the generic entity
system. ``tools/kampuscrave_provider.py`` — the one live chat-facing demo
path this migration touches — depends only on ``MenuRepository`` and does
not change at all; only what gets constructed and injected into it changes
(see tools/registry.py).

A menu item's ``name`` doubles as the entity row's id — the same
"upsert by natural key" semantics ``SqliteMenuRepository`` used to give via
``name TEXT PRIMARY KEY``, now expressed as this adapter's own convention
rather than the entity system needing to know about it.
"""

from adaptive_agent.entities.base import EntityRepository
from adaptive_agent.menu.base import MenuItem


class EntityBackedMenuRepository:
    """Implements MenuRepository."""

    def __init__(self, entity_repository: EntityRepository, table_name: str) -> None:
        self._entity_repository = entity_repository
        self._table_name = table_name

    def get_item(self, name: str) -> MenuItem | None:
        row = self._entity_repository.get_row(self._table_name, row_id=name)
        if row is None:
            return None
        return self._item_from_row(row)

    def list_items(self) -> list[MenuItem]:
        rows = self._entity_repository.list_rows(self._table_name)
        return [self._item_from_row(row) for row in rows]

    def seed(self, items: list[MenuItem]) -> None:
        for item in items:
            self._entity_repository.upsert_row(self._table_name, self._row_from_item(item))

    def delete_item(self, name: str) -> bool:
        return self._entity_repository.delete_row(self._table_name, row_id=name)

    @staticmethod
    def _item_from_row(row: dict) -> MenuItem:
        return MenuItem(
            name=row["name"],
            category=row["category"],
            price=row["price"],
            stock_quantity=row["stock_quantity"],
        )

    @staticmethod
    def _row_from_item(item: MenuItem) -> dict:
        return {
            "id": item.name,
            "name": item.name,
            "category": item.category,
            "price": item.price,
            "stock_quantity": item.stock_quantity,
        }
