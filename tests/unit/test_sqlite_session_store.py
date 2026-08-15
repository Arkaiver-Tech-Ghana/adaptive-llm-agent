from pathlib import Path

from adaptive_agent.llm.tool_types import ToolCall
from adaptive_agent.session.base import ConfirmationRequest
from adaptive_agent.session.sqlite_store import _SWEEP_INTERVAL, SqliteSessionStore


def _store(tmp_path: Path, **kwargs) -> SqliteSessionStore:
    return SqliteSessionStore(tmp_path / "sessions.sqlite3", **kwargs)


def test_get_history_is_empty_for_unknown_key(tmp_path):
    store = _store(tmp_path)
    assert store.get_history("session-a") == []


def test_history_accumulates_across_multiple_appends_for_same_key(tmp_path):
    store = _store(tmp_path)
    store.append("session-a", "user", "hi")
    store.append("session-a", "assistant", "hello")
    assert store.get_history("session-a") == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]


def test_history_is_isolated_between_different_keys(tmp_path):
    store = _store(tmp_path)
    store.append("session-a", "user", "hi from a")
    store.append("session-b", "user", "hi from b")
    assert store.get_history("session-a") == [{"role": "user", "content": "hi from a"}]
    assert store.get_history("session-b") == [{"role": "user", "content": "hi from b"}]


def test_get_pending_confirmation_is_none_when_unset(tmp_path):
    store = _store(tmp_path)
    assert store.get_pending_confirmation("session-a") is None


def test_set_then_get_pending_confirmation_round_trips(tmp_path):
    store = _store(tmp_path)
    request = ConfirmationRequest(
        tool_call=ToolCall(id="call-1", name="book_room", arguments={"room_type": "suite"})
    )
    store.set_pending_confirmation("session-a", request)
    assert store.get_pending_confirmation("session-a") == request


def test_setting_none_clears_a_previously_set_confirmation(tmp_path):
    store = _store(tmp_path)
    request = ConfirmationRequest(
        tool_call=ToolCall(id="call-1", name="book_room", arguments={"room_type": "suite"})
    )
    store.set_pending_confirmation("session-a", request)
    store.set_pending_confirmation("session-a", None)
    assert store.get_pending_confirmation("session-a") is None


def test_pending_confirmation_survives_a_later_history_append(tmp_path):
    """append() and set_pending_confirmation() each read-modify-write the
    same row; neither may clobber the other's column."""
    store = _store(tmp_path)
    request = ConfirmationRequest(
        tool_call=ToolCall(id="call-1", name="book_room", arguments={"room_type": "suite"})
    )
    store.set_pending_confirmation("session-a", request)
    store.append("session-a", "user", "yes")
    assert store.get_pending_confirmation("session-a") == request
    assert store.get_history("session-a") == [{"role": "user", "content": "yes"}]


def test_persistence_survives_a_simulated_process_restart(tmp_path):
    """The actual point of this change: two SqliteSessionStore instances
    pointed at the same file, simulating a process restart between them."""
    db_path = tmp_path / "sessions.sqlite3"
    request = ConfirmationRequest(
        tool_call=ToolCall(id="call-1", name="book_room", arguments={"room_type": "suite"})
    )

    first = SqliteSessionStore(db_path)
    first.append("session-a", "user", "book me a suite")
    first.append("session-a", "assistant", "you sure?")
    first.set_pending_confirmation("session-a", request)

    second = SqliteSessionStore(db_path)
    assert second.get_history("session-a") == [
        {"role": "user", "content": "book me a suite"},
        {"role": "assistant", "content": "you sure?"},
    ]
    assert second.get_pending_confirmation("session-a") == request


def test_idle_eviction_sweep_drops_stale_sessions_but_keeps_active_ones(tmp_path):
    now = [1_000_000.0]
    store = _store(tmp_path, idle_ttl_seconds=100, now_fn=lambda: now[0])

    store.append("stale-session", "user", "hi")

    now[0] += 200  # past the 100s TTL
    store.append("active-session", "user", "hi")

    # _maybe_sweep_locked only sweeps every _SWEEP_INTERVAL writes.
    for _ in range(_SWEEP_INTERVAL - 1):
        store.append("active-session", "assistant", "ok")

    assert store.get_history("stale-session") == []
    assert store.get_history("active-session") != []
