"""A second concrete LLM provider — Google's Gemini API — proving the LLM
axis is swappable per Business Config, per CLAUDE.md's invariant."""

import uuid
from typing import Any

from google import genai
from google.genai import types

from adaptive_agent.llm.base import LLMResponse
from adaptive_agent.llm.tool_types import ToolCall, ToolSpec

_ROLE_MAP = {"user": "user", "assistant": "model"}


class GoogleLLMProvider:
    """Implements LLMProvider. Reads GOOGLE_API_KEY (or GEMINI_API_KEY) from
    the environment.

    Unlike anthropic.Anthropic(), genai.Client() validates the API key
    eagerly at construction time, so the client is built lazily on first
    ``generate()`` call — constructing this provider must not require the
    key to be present (registry/wiring tests build providers without one).
    """

    def __init__(self, model: str):
        self._model = model
        self._client: genai.Client | None = None

    def generate(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        if self._client is None:
            self._client = genai.Client()

        contents = _to_native_contents(messages)

        config_kwargs: dict[str, Any] = {
            "system_instruction": system,
            "max_output_tokens": max_tokens,
        }
        if tools:
            config_kwargs["tools"] = [
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=t.name,
                            description=t.description,
                            parameters_json_schema=t.input_schema,
                        )
                        for t in tools
                    ]
                )
            ]

        response = self._client.models.generate_content(
            model=self._model,
            contents=contents,
            config=types.GenerateContentConfig(**config_kwargs),
        )

        parts = []
        if response.candidates and response.candidates[0].content:
            parts = response.candidates[0].content.parts or []

        text = "".join(p.text for p in parts if p.text)
        tool_calls = [
            ToolCall(
                # Gemini doesn't always populate function_call.id (e.g. when
                # there's only ever one call in flight) — fall back to a
                # generated id so every ToolCall this provider returns is
                # addressable by the Tool Rail / continue_with_tool_result.
                id=p.function_call.id or uuid.uuid4().hex,
                name=p.function_call.name,
                arguments=dict(p.function_call.args or {}),
            )
            for p in parts
            if p.function_call is not None
        ]
        return LLMResponse(text=text, tool_calls=tool_calls, raw=response)


def _to_native_contents(messages: list[dict[str, Any]]) -> list[types.Content]:
    """Translate normalized messages (see llm/base.py's module docstring)
    into Gemini's native ``Content``/``Part`` shape. Google's
    ``FunctionResponse`` requires the original Tool *name*, not just the
    call id it's answering — but the normalized tool-result shape only
    carries ``tool_call_id`` (Anthropic's ``tool_result`` block doesn't need
    a name). So this first indexes every ``tool_calls`` entry seen earlier
    in the transcript by id, then uses that to fill in ``name`` when
    translating each ``tool`` turn."""
    call_names: dict[str, str] = {}
    for message in messages:
        if message.get("role") == "assistant":
            for call in message.get("tool_calls") or []:
                call_names[call["id"]] = call["name"]

    return [_to_native_content(m, call_names) for m in messages]


def _to_native_content(message: dict[str, Any], call_names: dict[str, str]) -> types.Content:
    role = message["role"]

    if role == "tool":
        call_id = message["tool_call_id"]
        return types.Content(
            role="user",
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        id=call_id,
                        name=call_names.get(call_id, ""),
                        response={"output": message["content"]},
                    )
                )
            ],
        )

    if role == "assistant" and message.get("tool_calls"):
        parts = []
        if message.get("content"):
            parts.append(types.Part(text=message["content"]))
        for call in message["tool_calls"]:
            parts.append(
                types.Part(
                    function_call=types.FunctionCall(
                        id=call["id"], name=call["name"], args=call["arguments"]
                    )
                )
            )
        return types.Content(role="model", parts=parts)

    return types.Content(role=_ROLE_MAP[role], parts=[types.Part(text=message["content"])])
