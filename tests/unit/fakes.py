"""Test doubles implementing production Protocols, for network-free unit tests."""

from adaptive_agent.llm.base import LLMResponse


class FakeLLMProvider:
    """Implements LLMProvider. Records the call it received, returns a canned reply."""

    def __init__(self, canned_text: str = "canned response"):
        self.canned_text = canned_text
        self.last_system: str | None = None
        self.last_messages: list[dict[str, str]] | None = None
        self.last_max_tokens: int | None = None

    def generate(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int,
    ) -> LLMResponse:
        self.last_system = system
        self.last_messages = messages
        self.last_max_tokens = max_tokens
        return LLMResponse(text=self.canned_text)
