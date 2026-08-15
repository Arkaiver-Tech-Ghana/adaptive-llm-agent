"""Test doubles implementing production Protocols, for network-free unit tests."""

from typing import Any

from adaptive_agent.llm.base import LLMResponse
from adaptive_agent.llm.tool_types import ToolCall, ToolSpec
from adaptive_agent.rails.base import RailVerdict


class FakeLLMProvider:
    """Implements LLMProvider. Records the call it received, returns a canned reply."""

    def __init__(
        self,
        canned_text: str = "canned response",
        canned_tool_calls: list[ToolCall] | None = None,
    ):
        self.canned_text = canned_text
        self.canned_tool_calls = canned_tool_calls or []
        self.last_system: str | None = None
        self.last_messages: list[dict[str, Any]] | None = None
        self.last_max_tokens: int | None = None
        self.last_tools: list[ToolSpec] | None = None

    def generate(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        self.last_system = system
        self.last_messages = messages
        self.last_max_tokens = max_tokens
        self.last_tools = tools
        return LLMResponse(text=self.canned_text, tool_calls=self.canned_tool_calls)


class FakeToolProvider:
    """Implements ToolProvider. Records the call it received, returns a canned result."""

    def __init__(self, canned_result: Any = None):
        self.canned_result = canned_result
        self.last_name: str | None = None
        self.last_arguments: dict[str, Any] | None = None

    def call(self, name: str, arguments: dict[str, Any]) -> Any:
        self.last_name = name
        self.last_arguments = arguments
        return self.canned_result


class FakeSessionStore:
    """Implements just enough of SessionStore for FakeConversationRuntime's
    ``session_store.get_pending_confirmation`` surface — InterfaceLayer
    only ever reads pending-confirmation state after a handle_message call,
    never history."""

    def __init__(self) -> None:
        self._pending: dict[str, Any] = {}

    def get_pending_confirmation(self, session_key: str) -> Any:
        return self._pending.get(session_key)

    def set_pending_confirmation(self, session_key: str, request: Any) -> None:
        self._pending[session_key] = request


class FakeConversationRuntime:
    """Implements the subset of ConversationRuntime's surface InterfaceLayer
    calls: ``handle_message`` and ``.session_store.get_pending_confirmation``.
    Records every handle_message call so tests can assert it was (or
    wasn't) reached, e.g. by dedupe/rate-limit short-circuiting."""

    def __init__(
        self, canned_reply: str = "canned reply", pending_after_reply: Any = None
    ):
        self.canned_reply = canned_reply
        self.pending_after_reply = pending_after_reply
        self.session_store = FakeSessionStore()
        self.calls: list[tuple[str, str]] = []

    def handle_message(self, session_key: str, user_message: str) -> str:
        self.calls.append((session_key, user_message))
        self.session_store.set_pending_confirmation(session_key, self.pending_after_reply)
        return self.canned_reply


class FakeCustomerStore:
    """Implements CustomerStore. Records every customer_id record_visit
    was called with, in call order."""

    def __init__(self) -> None:
        self.visits: list[str] = []

    def record_visit(self, customer_id: str) -> None:
        self.visits.append(customer_id)


class FakeMenuRepository:
    """Implements MenuRepository. In-memory dict keyed by item name."""

    def __init__(self, items: list[Any] | None = None):
        self._items: dict[str, Any] = {item.name: item for item in (items or [])}
        self.seeded: list[Any] = []

    def get_item(self, name: str) -> Any:
        return self._items.get(name)

    def list_items(self) -> list[Any]:
        return list(self._items.values())

    def seed(self, items: list[Any]) -> None:
        self.seeded.extend(items)
        for item in items:
            self._items[item.name] = item


class FakeRailChecker:
    """Implements RailChecker. Canned allow/block verdicts, records the last
    message each method was asked to check."""

    def __init__(self, blocks_input: bool = False, blocks_output: bool = False):
        self.blocks_input = blocks_input
        self.blocks_output = blocks_output
        self.last_input_checked: str | None = None
        self.last_output_checked: str | None = None

    def check_input(self, message: str) -> RailVerdict:
        self.last_input_checked = message
        if self.blocks_input:
            return RailVerdict(allowed=False, text="blocked", activated_rail="self check input")
        return RailVerdict(allowed=True, text=message, activated_rail=None)

    def check_output(self, response_text: str) -> RailVerdict:
        self.last_output_checked = response_text
        if self.blocks_output:
            return RailVerdict(allowed=False, text="blocked", activated_rail="self check output")
        return RailVerdict(allowed=True, text=response_text, activated_rail=None)
