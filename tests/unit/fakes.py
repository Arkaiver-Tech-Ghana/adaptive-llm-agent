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
