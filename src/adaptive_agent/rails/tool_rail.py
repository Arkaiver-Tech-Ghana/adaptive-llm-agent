"""The Tool Rail — governs which Tools the Agent Core may call and gates
write/irreversible Tool calls behind a Confirmation (CONTEXT.md).

Pure function, no I/O: there is only ever one real strategy for this
decision, so unlike the Rail Checker (NeMo-backed, genuinely swappable) this
doesn't need a Protocol or a fake.
"""

from enum import Enum

from adaptive_agent.business_config.schema import ToolConfig
from adaptive_agent.llm.tool_types import ToolCall


class ToolRailDecision(str, Enum):
    ALLOW = "allow"
    REQUIRE_CONFIRMATION = "require_confirmation"
    DENY = "deny"  # tool name not found in this Business's tool list — hallucination guard


def decide(tool_call: ToolCall, tool_configs: list[ToolConfig]) -> ToolRailDecision:
    for tool_config in tool_configs:
        if tool_config.name == tool_call.name:
            if not tool_config.enabled:
                return ToolRailDecision.DENY
            if tool_config.requires_confirmation:
                return ToolRailDecision.REQUIRE_CONFIRMATION
            return ToolRailDecision.ALLOW
    return ToolRailDecision.DENY
