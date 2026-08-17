import pytest

from adaptive_agent.tools.base import UnknownToolError
from adaptive_agent.tools.composite_provider import CompositeToolProvider


class _FixedProvider:
    def __init__(self, name: str, result):
        self._name = name
        self._result = result

    def call(self, name, arguments):
        if name != self._name:
            raise UnknownToolError(f"Unknown tool: {name!r}")
        return self._result


def test_dispatches_to_the_provider_that_recognizes_the_name():
    # Mirrors the real chain wired in conversation.py: the Business's own
    # provider, then entity-CRUD, then MCP last.
    composite = CompositeToolProvider(
        [
            _FixedProvider("book_room", "room booked"),
            _FixedProvider("create_notes", "note created"),
            _FixedProvider("proxied_tool", "proxied"),
        ]
    )

    assert composite.call("book_room", {}) == "room booked"
    assert composite.call("create_notes", {}) == "note created"
    assert composite.call("proxied_tool", {}) == "proxied"


def test_unknown_name_across_every_provider_raises_the_last_providers_error():
    composite = CompositeToolProvider(
        [
            _FixedProvider("book_room", "x"),
            _FixedProvider("create_notes", "y"),
            _FixedProvider("proxied_tool", "z"),
        ]
    )

    with pytest.raises(UnknownToolError):
        composite.call("nonexistent_tool", {})


def test_requires_at_least_one_provider():
    with pytest.raises(ValueError):
        CompositeToolProvider([])
