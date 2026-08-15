"""The one concrete LLM provider Day 1 ships: Anthropic's Claude API."""

from typing import Any

import anthropic

from adaptive_agent.llm.base import LLMResponse
from adaptive_agent.llm.tool_types import ToolCall, ToolSpec


class AnthropicLLMProvider:
    """Implements LLMProvider. Reads ANTHROPIC_API_KEY from the environment."""

    def __init__(self, model: str, effort: str | None = None):
        self._client = anthropic.Anthropic()
        self._model = model
        self._effort = effort

    def generate(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        kwargs: dict = {}
        if self._effort:
            kwargs["output_config"] = {"effort": self._effort}
        if tools:
            kwargs["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.input_schema}
                for t in tools
            ]

        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[_to_native_message(m) for m in messages],
            **kwargs,
        )

        text = next((block.text for block in response.content if block.type == "text"), "")
        tool_calls = [
            ToolCall(id=block.id, name=block.name, arguments=block.input)
            for block in response.content
            if block.type == "tool_use"
        ]
        return LLMResponse(text=text, tool_calls=tool_calls, raw=response)


def _to_native_message(message: dict[str, Any]) -> dict[str, Any]:
    """Translate one normalized message (see llm/base.py's module docstring)
    into Anthropic's native content-block shape. Plain user/assistant text
    turns pass through as a flat string; an assistant turn carrying
    ``tool_calls`` expands into ``tool_use`` blocks, and a ``tool`` turn
    becomes a user message carrying a ``tool_result`` block."""
    role = message["role"]

    if role == "tool":
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": message["tool_call_id"],
                    "content": message["content"],
                }
            ],
        }

    if role == "assistant" and message.get("tool_calls"):
        content: list[dict[str, Any]] = []
        if message.get("content"):
            content.append({"type": "text", "text": message["content"]})
        for call in message["tool_calls"]:
            content.append(
                {
                    "type": "tool_use",
                    "id": call["id"],
                    "name": call["name"],
                    "input": call["arguments"],
                }
            )
        return {"role": "assistant", "content": content}

    return {"role": role, "content": message["content"]}
