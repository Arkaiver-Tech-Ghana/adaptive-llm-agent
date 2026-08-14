"""The pluggable LLM axis. Business Config selects a provider by name; the
Agent Core only ever depends on this Protocol, never a concrete provider."""

from typing import Any, Protocol

from pydantic import BaseModel


class LLMResponse(BaseModel):
    text: str
    raw: Any = None

    model_config = {"arbitrary_types_allowed": True}


class LLMProvider(Protocol):
    def generate(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int,
    ) -> LLMResponse: ...
