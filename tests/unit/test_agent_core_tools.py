from pathlib import Path

from adaptive_agent.agent_core import AgentCore
from adaptive_agent.business_config.schema import BusinessConfig
from adaptive_agent.context.file_provider import FileContextProvider
from adaptive_agent.llm.tool_types import ToolCall, ToolSpec
from tests.unit.fakes import FakeLLMProvider

FIXTURES = Path(__file__).parent / "fixtures" / "context_files"

CONFIG = BusinessConfig.model_validate(
    {
        "business_id": "hotelbiz",
        "display_name": "Test Hotel",
        "llm": {"max_tokens": 512},
        "context": {"directory": "context_files", "include_patterns": ["*.md"]},
        "business_logic": {
            "persona": "You are the Test Hotel assistant.",
            "scope_instructions": "Answer only from context.",
        },
        "tools": [
            {
                "name": "check_room_availability",
                "description": "Check whether a room type is available.",
                "input_schema": {
                    "type": "object",
                    "properties": {"room_type": {"type": "string"}},
                    "required": ["room_type"],
                },
            },
            {
                "name": "book_room",
                "description": "Book a room.",
                "input_schema": {
                    "type": "object",
                    "properties": {"room_type": {"type": "string"}},
                    "required": ["room_type"],
                },
                "requires_confirmation": True,
            },
        ],
    }
)


def _build_core(fake: FakeLLMProvider) -> AgentCore:
    context_provider = FileContextProvider(FIXTURES, include_patterns=["*.md"])
    return AgentCore(CONFIG, fake, context_provider)


def test_tool_specs_derived_from_business_config_tools():
    fake = FakeLLMProvider()
    core = _build_core(fake)
    specs = core.tool_specs
    assert specs == [
        ToolSpec(
            name="check_room_availability",
            description="Check whether a room type is available.",
            input_schema={
                "type": "object",
                "properties": {"room_type": {"type": "string"}},
                "required": ["room_type"],
            },
        ),
        ToolSpec(
            name="book_room",
            description="Book a room.",
            input_schema={
                "type": "object",
                "properties": {"room_type": {"type": "string"}},
                "required": ["room_type"],
            },
        ),
    ]


def test_tool_specs_excludes_disabled_tools():
    config = BusinessConfig.model_validate(
        {**CONFIG.model_dump(mode="json"), "tools": [
            {
                "name": "check_room_availability",
                "description": "Check whether a room type is available.",
                "input_schema": {"type": "object"},
            },
            {
                "name": "book_room",
                "description": "Book a room.",
                "input_schema": {"type": "object"},
                "enabled": False,
            },
        ]}
    )
    core = AgentCore(config, FakeLLMProvider(), FileContextProvider(FIXTURES, include_patterns=["*.md"]))
    assert [spec.name for spec in core.tool_specs] == ["check_room_availability"]


def test_respond_with_tools_passes_tools_through_to_provider():
    fake = FakeLLMProvider()
    core = _build_core(fake)
    core.respond_with_tools("any deluxe rooms?", history=None, tools=core.tool_specs)
    assert fake.last_tools == core.tool_specs


def test_respond_with_tools_returns_full_llm_response_with_tool_calls():
    canned_call = ToolCall(
        id="call_1", name="check_room_availability", arguments={"room_type": "deluxe"}
    )
    fake = FakeLLMProvider(canned_text="", canned_tool_calls=[canned_call])
    core = _build_core(fake)
    result = core.respond_with_tools("any deluxe rooms?", history=None, tools=core.tool_specs)
    assert result.tool_calls == [canned_call]
    assert result.text == ""


def test_respond_with_tools_builds_system_prompt_and_includes_history_and_message():
    fake = FakeLLMProvider()
    core = _build_core(fake)
    history = [{"role": "user", "content": "earlier"}, {"role": "assistant", "content": "reply"}]
    core.respond_with_tools("follow up", history=history, tools=core.tool_specs)
    assert fake.last_system is not None
    assert "You are the Test Hotel assistant." in fake.last_system
    assert fake.last_messages == [*history, {"role": "user", "content": "follow up"}]
    assert fake.last_max_tokens == 512


def test_continue_with_tool_result_assembles_expected_message_sequence():
    fake = FakeLLMProvider(canned_text="Yes, it's available.")
    core = _build_core(fake)
    history = [{"role": "user", "content": "any deluxe rooms?"}]
    tool_call = ToolCall(
        id="call_1", name="check_room_availability", arguments={"room_type": "deluxe"}
    )
    tool_result = {"available": True}

    result = core.continue_with_tool_result(history, tool_call, tool_result)

    assert fake.last_messages == [
        {"role": "user", "content": "any deluxe rooms?"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "name": "check_room_availability",
                    "arguments": {"room_type": "deluxe"},
                    "provider_data": None,
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": '{"available": true}'},
    ]
    assert result.text == "Yes, it's available."


def test_continue_with_tool_result_calls_generate_without_tools():
    fake = FakeLLMProvider()
    core = _build_core(fake)
    tool_call = ToolCall(id="call_1", name="check_room_availability", arguments={})
    core.continue_with_tool_result([], tool_call, {"available": True})
    assert fake.last_tools is None
