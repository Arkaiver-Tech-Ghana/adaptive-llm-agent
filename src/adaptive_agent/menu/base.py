"""The storage-agnostic contract for KampusCrave's live menu data.

``check_menu_item`` (tools/kampuscrave_provider.py) talks only to this
Protocol, never to SQLite directly — a different backend later means
writing a new class against ``MenuRepository``, nothing above the
repository layer changes.
"""

from typing import Protocol

from pydantic import BaseModel


class MenuItem(BaseModel):
    name: str
    category: str
    price: float
    stock_quantity: int


class MenuRepository(Protocol):
    def get_item(self, name: str) -> MenuItem | None: ...
    def list_items(self) -> list[MenuItem]: ...
    def seed(self, items: list[MenuItem]) -> None: ...  # idempotent
