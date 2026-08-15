"""KampusCrave's first real Tool backend: a read-only lookup against a
live MenuRepository, replacing static prose (context/menu.md) as the
source of truth for price/stock questions. General menu browsing still
comes from menu.md via the Data Rail's context-doc path — this Tool only
answers a specific item's authoritative price and stock.

Constructed with a MenuRepository (dependency injection) — never touches
SQLite directly, so a different backend later is a new MenuRepository
implementation, not a change here.
"""

from typing import Any

from adaptive_agent.menu.base import MenuRepository
from adaptive_agent.tools.base import UnknownToolError


class KampusCraveToolProvider:
    """Implements ToolProvider."""

    def __init__(self, menu_repository: MenuRepository) -> None:
        self.menu_repository = menu_repository

    def call(self, name: str, arguments: dict[str, Any]) -> Any:
        if name == "check_menu_item":
            return self._check_menu_item(arguments)
        raise UnknownToolError(f"Unknown tool: {name!r}")

    def _check_menu_item(self, arguments: dict[str, Any]) -> dict[str, Any]:
        item_name = arguments["item_name"]
        item = self.menu_repository.get_item(item_name)
        if item is None:
            # Unknown item name is a normal "not found" answer, not an
            # error — matches InMemoryToolProvider's convention: only an
            # unknown tool *name* raises, never a bad argument.
            return {
                "found": False,
                "item_name": item_name,
                "reason": f"No such menu item: {item_name!r}",
            }
        return {
            "found": True,
            "item_name": item.name,
            "category": item.category,
            "price": item.price,
            "stock_quantity": item.stock_quantity,
        }
