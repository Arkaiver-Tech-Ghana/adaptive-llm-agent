"""Tool-calling behavior of AnthropicLLMProvider: SDK request/response
translation at the ``self._client.messages.create`` boundary. The
underlying SDK client call is stubbed (same record-then-assert idiom as
tests/unit/fakes.py) rather than hitting the network."""

from types import SimpleNamespace

from adaptive_agent.llm.anthropic_provider import AnthropicLLMProvider
from adaptive_agent.llm.tool_types import ToolSpec


def _text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def _tool_use_block(id_: str, name: str, input_: dict) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=id_, name=name, input=input_)


def _build_provider() -> AnthropicLLMProvider:
    provider = AnthropicLLMProvider.__new__(AnthropicLLMProvider)
    provider._client = SimpleNamespace(messages=SimpleNamespace(create=None))
    provider._model = "claude-sonnet-5"
    provider._effort = None
    return provider


TOOL = ToolSpec(
    name="check_room_availability",
    description="Check whether a room type is available for given dates.",
    input_schema={
        "type": "object",
        "properties": {"room_type": {"type": "string"}},
        "required": ["room_type"],
    },
)


def test_generate_passes_tools_to_sdk():
    provider = _build_provider()
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(content=[_text_block("ok")])

    provider._client.messages.create = fake_create

    provider.generate(
        system="sys",
        messages=[{"role": "user", "content": "any rooms free?"}],
        max_tokens=100,
        tools=[TOOL],
    )

    assert captured["tools"] == [
        {
            "name": "check_room_availability",
            "description": "Check whether a room type is available for given dates.",
            "input_schema": TOOL.input_schema,
        }
    ]


def test_generate_parses_tool_use_block_into_tool_calls():
    provider = _build_provider()

    def fake_create(**kwargs):
        return SimpleNamespace(
            content=[
                _tool_use_block("call_1", "check_room_availability", {"room_type": "deluxe"})
            ]
        )

    provider._client.messages.create = fake_create

    result = provider.generate(
        system="sys",
        messages=[{"role": "user", "content": "any deluxe rooms free?"}],
        max_tokens=100,
        tools=[TOOL],
    )

    assert result.text == ""
    assert len(result.tool_calls) == 1
    call = result.tool_calls[0]
    assert call.id == "call_1"
    assert call.name == "check_room_availability"
    assert call.arguments == {"room_type": "deluxe"}


def test_generate_extracts_text_alongside_tool_use_block():
    provider = _build_provider()

    def fake_create(**kwargs):
        return SimpleNamespace(
            content=[
                _text_block("Let me check that for you."),
                _tool_use_block("call_1", "check_room_availability", {"room_type": "deluxe"}),
            ]
        )

    provider._client.messages.create = fake_create

    result = provider.generate(
        system="sys", messages=[{"role": "user", "content": "hi"}], max_tokens=100
    )

    assert result.text == "Let me check that for you."
    assert len(result.tool_calls) == 1


def test_generate_translates_tool_call_and_tool_result_messages():
    provider = _build_provider()
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(content=[_text_block("Yes, it's available.")])

    provider._client.messages.create = fake_create

    messages = [
        {"role": "user", "content": "any deluxe rooms free?"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "call_1", "name": "check_room_availability", "arguments": {"room_type": "deluxe"}}
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": '{"available": true}'},
    ]

    provider.generate(system="sys", messages=messages, max_tokens=100)

    native = captured["messages"]
    assert native[0] == {"role": "user", "content": "any deluxe rooms free?"}
    assert native[1] == {
        "role": "assistant",
        "content": [
            {
                "type": "tool_use",
                "id": "call_1",
                "name": "check_room_availability",
                "input": {"room_type": "deluxe"},
            }
        ],
    }
    assert native[2] == {
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "call_1", "content": '{"available": true}'}
        ],
    }
