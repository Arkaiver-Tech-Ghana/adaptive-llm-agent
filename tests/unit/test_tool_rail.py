from adaptive_agent.business_config.schema import ToolConfig
from adaptive_agent.llm.tool_types import ToolCall
from adaptive_agent.rails.tool_rail import ToolRailDecision, decide

READ_TOOL = ToolConfig(name="check_room_availability", requires_confirmation=False)
WRITE_TOOL = ToolConfig(name="book_room", requires_confirmation=True)
TOOL_CONFIGS = [READ_TOOL, WRITE_TOOL]


def _call(name: str) -> ToolCall:
    return ToolCall(id="call-1", name=name, arguments={})


def test_known_tool_without_confirmation_is_allowed():
    assert decide(_call("check_room_availability"), TOOL_CONFIGS) == ToolRailDecision.ALLOW


def test_known_tool_requiring_confirmation_requires_confirmation():
    assert decide(_call("book_room"), TOOL_CONFIGS) == ToolRailDecision.REQUIRE_CONFIRMATION


def test_unknown_tool_name_is_denied():
    assert decide(_call("delete_hotel"), TOOL_CONFIGS) == ToolRailDecision.DENY


def test_empty_tool_configs_denies_everything():
    assert decide(_call("check_room_availability"), []) == ToolRailDecision.DENY
