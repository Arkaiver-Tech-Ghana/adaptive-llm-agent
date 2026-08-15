from adaptive_agent.llm.tool_types import ToolCall
from adaptive_agent.session.base import ConfirmationRequest
from adaptive_agent.session.in_memory import InMemorySessionStore


def test_get_history_is_empty_for_unknown_key():
    store = InMemorySessionStore()
    assert store.get_history("session-a") == []


def test_history_accumulates_across_multiple_appends_for_same_key():
    store = InMemorySessionStore()
    store.append("session-a", "user", "hi")
    store.append("session-a", "assistant", "hello")
    assert store.get_history("session-a") == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]


def test_history_is_isolated_between_different_keys():
    store = InMemorySessionStore()
    store.append("session-a", "user", "hi from a")
    store.append("session-b", "user", "hi from b")
    assert store.get_history("session-a") == [{"role": "user", "content": "hi from a"}]
    assert store.get_history("session-b") == [{"role": "user", "content": "hi from b"}]


def test_get_pending_confirmation_is_none_when_unset():
    store = InMemorySessionStore()
    assert store.get_pending_confirmation("session-a") is None


def test_set_then_get_pending_confirmation_round_trips():
    store = InMemorySessionStore()
    request = ConfirmationRequest(
        tool_call=ToolCall(id="call-1", name="book_room", arguments={"room_type": "suite"})
    )
    store.set_pending_confirmation("session-a", request)
    assert store.get_pending_confirmation("session-a") == request


def test_setting_none_clears_a_previously_set_confirmation():
    store = InMemorySessionStore()
    request = ConfirmationRequest(
        tool_call=ToolCall(id="call-1", name="book_room", arguments={"room_type": "suite"})
    )
    store.set_pending_confirmation("session-a", request)
    store.set_pending_confirmation("session-a", None)
    assert store.get_pending_confirmation("session-a") is None
