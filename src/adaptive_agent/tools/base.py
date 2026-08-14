"""The pluggable tools axis — stub. Not wired into the Agent Core Day 1.

Tool-calling and the Tool Rail's confirmation gate ship Day 2 (see
prd-adaptive-agent.md and CLAUDE.md's rails section). This Protocol exists
now so a real ToolProvider slots in later without touching agent_core.py.
"""

from typing import Any, Protocol


class ToolProvider(Protocol):
    def call(self, name: str, arguments: dict[str, Any]) -> Any: ...
