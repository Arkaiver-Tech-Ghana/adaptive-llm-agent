"""Test doubles implementing production Protocols, for network-free unit tests."""

from typing import Any

from adaptive_agent.llm.base import LLMResponse
from adaptive_agent.llm.tool_types import ToolCall, ToolSpec


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
