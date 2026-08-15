import pytest

from adaptive_agent.tools.in_memory_provider import InMemoryToolProvider
from adaptive_agent.tools.kampuscrave_provider import KampusCraveToolProvider
from adaptive_agent.tools.registry import UnknownToolProviderError, build_tool_provider


def test_build_tool_provider_for_hotel_returns_in_memory_provider(tmp_path):
    provider = build_tool_provider("hotel", tmp_path / "hotel.sqlite3")
    assert isinstance(provider, InMemoryToolProvider)


def test_build_tool_provider_for_kampuscrave_returns_kampuscrave_provider(tmp_path):
    provider = build_tool_provider("kampuscrave", tmp_path / "kampuscrave.sqlite3")
    assert isinstance(provider, KampusCraveToolProvider)


def test_unknown_business_id_raises_helpful_error(tmp_path):
    with pytest.raises(UnknownToolProviderError, match="unknown-biz"):
        build_tool_provider("unknown-biz", tmp_path / "unknown.sqlite3")
