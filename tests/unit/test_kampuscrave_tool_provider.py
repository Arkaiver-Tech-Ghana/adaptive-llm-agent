import pytest

from adaptive_agent.menu.base import MenuItem
from adaptive_agent.tools.base import UnknownToolError
from adaptive_agent.tools.kampuscrave_provider import KampusCraveToolProvider
from tests.unit.fakes import FakeMenuRepository


def test_check_menu_item_returns_live_price_and_stock():
    item = MenuItem(name="Veggie Burger", category="burgers", price=6.0, stock_quantity=10)
    provider = KampusCraveToolProvider(FakeMenuRepository([item]))

    result = provider.call("check_menu_item", {"item_name": "Veggie Burger"})

    assert result["found"] is True
    assert result["price"] == 6.0
    assert result["stock_quantity"] == 10


def test_check_menu_item_for_unknown_item_is_a_normal_not_found_result():
    provider = KampusCraveToolProvider(FakeMenuRepository())

    result = provider.call("check_menu_item", {"item_name": "Caviar"})

    assert result["found"] is False
    assert result["item_name"] == "Caviar"


def test_unknown_tool_name_raises_unknown_tool_error():
    provider = KampusCraveToolProvider(FakeMenuRepository())

    with pytest.raises(UnknownToolError):
        provider.call("place_order", {})
