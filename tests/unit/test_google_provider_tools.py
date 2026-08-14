"""Tool-calling behavior of GoogleLLMProvider: SDK request/response
translation at the ``self._client.models.generate_content`` boundary. The
underlying SDK client call is stubbed (same record-then-assert idiom as
tests/unit/fakes.py) rather than hitting the network."""

import base64
from types import SimpleNamespace

from google.genai import types

from adaptive_agent.llm.google_provider import GoogleLLMProvider
from adaptive_agent.llm.tool_types import ToolSpec

TOOL = ToolSpec(
    name="check_room_availability",
    description="Check whether a room type is available for given dates.",
    input_schema={
        "type": "object",
        "properties": {"room_type": {"type": "string"}},
        "required": ["room_type"],
    },
)


def _build_provider() -> GoogleLLMProvider:
    provider = GoogleLLMProvider.__new__(GoogleLLMProvider)
    provider._model = "gemini-flash-latest"
    provider._client = SimpleNamespace(models=SimpleNamespace(generate_content=None))
    return provider


def _candidate_response(parts: list) -> SimpleNamespace:
    return SimpleNamespace(
        candidates=[SimpleNamespace(content=SimpleNamespace(parts=parts))]
    )


def test_generate_passes_tools_to_sdk():
    provider = _build_provider()
    captured = {}

    def fake_generate_content(**kwargs):
        captured.update(kwargs)
        return _candidate_response([SimpleNamespace(text="ok", function_call=None)])

    provider._client.models.generate_content = fake_generate_content

    provider.generate(
        system="sys",
        messages=[{"role": "user", "content": "any rooms free?"}],
        max_tokens=100,
        tools=[TOOL],
    )

    config = captured["config"]
    assert isinstance(config, types.GenerateContentConfig)
    assert len(config.tools) == 1
    decl = config.tools[0].function_declarations[0]
    assert decl.name == "check_room_availability"
    assert decl.description == "Check whether a room type is available for given dates."
    assert decl.parameters_json_schema == TOOL.input_schema


def test_generate_parses_function_call_part_into_tool_calls():
    provider = _build_provider()

    def fake_generate_content(**kwargs):
        return _candidate_response(
            [
                SimpleNamespace(
                    text=None,
                    function_call=SimpleNamespace(
                        id="call_1", name="check_room_availability", args={"room_type": "deluxe"}
                    ),
                )
            ]
        )

    provider._client.models.generate_content = fake_generate_content

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


def test_generate_assigns_fallback_id_when_sdk_omits_it():
    provider = _build_provider()

    def fake_generate_content(**kwargs):
        return _candidate_response(
            [
                SimpleNamespace(
                    text=None,
                    function_call=SimpleNamespace(
                        id=None, name="check_room_availability", args={"room_type": "deluxe"}
                    ),
                )
            ]
        )

    provider._client.models.generate_content = fake_generate_content

    result = provider.generate(
        system="sys", messages=[{"role": "user", "content": "hi"}], max_tokens=100
    )

    assert result.tool_calls[0].id
    assert isinstance(result.tool_calls[0].id, str)


def test_generate_extracts_text_alongside_function_call_part():
    provider = _build_provider()

    def fake_generate_content(**kwargs):
        return _candidate_response(
            [
                SimpleNamespace(text="Let me check that for you.", function_call=None),
                SimpleNamespace(
                    text=None,
                    function_call=SimpleNamespace(
                        id="call_1", name="check_room_availability", args={"room_type": "deluxe"}
                    ),
                ),
            ]
        )

    provider._client.models.generate_content = fake_generate_content

    result = provider.generate(
        system="sys", messages=[{"role": "user", "content": "hi"}], max_tokens=100
    )

    assert result.text == "Let me check that for you."
    assert len(result.tool_calls) == 1


def test_generate_captures_thought_signature_into_provider_data():
    """Gemini requires a replayed function-call Part to echo back the same
    thought_signature the model originally attached — dropped otherwise,
    it's a real 400 on the continuation turn (discovered live, see
    google_provider.py's _pack_thought_signature comment). This asserts the
    parsing half of that round trip: the response's opaque signature bytes
    land in ToolCall.provider_data, not silently discarded."""
    provider = _build_provider()

    def fake_generate_content(**kwargs):
        return _candidate_response(
            [
                SimpleNamespace(
                    text=None,
                    function_call=SimpleNamespace(
                        id="call_1", name="check_room_availability", args={"room_type": "deluxe"}
                    ),
                    thought_signature=b"opaque-signature-bytes",
                )
            ]
        )

    provider._client.models.generate_content = fake_generate_content

    result = provider.generate(
        system="sys", messages=[{"role": "user", "content": "hi"}], max_tokens=100
    )

    call = result.tool_calls[0]
    assert call.provider_data is not None
    assert "opaque-signature-bytes" not in str(call.provider_data)  # stored, not raw
    assert base64.b64decode(call.provider_data["google_thought_signature_b64"]) == b"opaque-signature-bytes"


def test_generate_replays_thought_signature_onto_the_function_call_part():
    """The other half of the round trip: a ToolCall carrying provider_data
    from a prior turn gets its thought_signature set back on the Part when
    replayed into a continuation call's ``contents``."""
    provider = _build_provider()
    captured = {}

    def fake_generate_content(**kwargs):
        captured.update(kwargs)
        return _candidate_response([SimpleNamespace(text="Yes, it's available.", function_call=None)])

    provider._client.models.generate_content = fake_generate_content

    encoded = base64.b64encode(b"opaque-signature-bytes").decode("ascii")
    messages = [
        {"role": "user", "content": "any deluxe rooms free?"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "name": "check_room_availability",
                    "arguments": {"room_type": "deluxe"},
                    "provider_data": {"google_thought_signature_b64": encoded},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": '{"available": true}'},
    ]

    provider.generate(system="sys", messages=messages, max_tokens=100)

    native = captured["contents"]
    assert native[1].parts[0].thought_signature == b"opaque-signature-bytes"


def test_generate_translates_tool_call_and_tool_result_messages():
    provider = _build_provider()
    captured = {}

    def fake_generate_content(**kwargs):
        captured.update(kwargs)
        return _candidate_response([SimpleNamespace(text="Yes, it's available.", function_call=None)])

    provider._client.models.generate_content = fake_generate_content

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

    native = captured["contents"]
    assert len(native) == 3

    assert native[0].role == "user"
    assert native[0].parts[0].text == "any deluxe rooms free?"

    assert native[1].role == "model"
    fc = native[1].parts[0].function_call
    assert fc.id == "call_1"
    assert fc.name == "check_room_availability"
    assert fc.args == {"room_type": "deluxe"}

    assert native[2].role == "user"
    fr = native[2].parts[0].function_response
    assert fr.id == "call_1"
    assert fr.name == "check_room_availability"
    assert fr.response == {"output": '{"available": true}'}
