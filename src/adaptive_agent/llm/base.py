"""The pluggable LLM axis. Business Config selects a provider by name; the
Agent Core only ever depends on this Protocol, never a concrete provider.

Normalized message shape
-------------------------
``messages`` is a list of dicts. Plain conversational turns keep the Day 1
shape (``{"role": "user"|"assistant", "content": "<text>"}``). Tool-calling
adds two more normalized turn shapes that every concrete ``LLMProvider``
must translate to/from its own SDK's native tool-calling representation
(Anthropic's ``tool_use``/``tool_result`` content blocks, Google's
``function_call``/``function_response`` parts) — neither SDK's native shape
leaks past this module:

- An assistant turn requesting a Tool call:
  ``{"role": "assistant", "content": "", "tool_calls": [<ToolCall.model_dump()>]}``
- A Tool-result turn answering that call:
  ``{"role": "tool", "tool_call_id": "<id>", "content": "<json-serialized result>"}``

Because these payloads are no longer flat str-to-str, ``messages`` is typed
as ``list[dict[str, Any]]`` rather than ``list[dict[str, str]]``.
"""

from typing import Any, Protocol

from pydantic import BaseModel, Field

from adaptive_agent.llm.tool_types import ToolCall, ToolSpec


class LLMResponse(BaseModel):
    text: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    raw: Any = None

    model_config = {"arbitrary_types_allowed": True}


class LLMProvider(Protocol):
    def generate(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse: ...
