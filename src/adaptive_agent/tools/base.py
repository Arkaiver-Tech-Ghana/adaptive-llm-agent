"""The pluggable tools axis — stub. Not wired into the Agent Core Day 1.

Tool-calling and the Tool Rail's confirmation gate ship Day 2 (see
prd-adaptive-agent.md and CLAUDE.md's rails section). This Protocol exists
now so a real ToolProvider slots in later without touching agent_core.py.
"""

from typing import Any, Protocol


class UnknownToolError(Exception):
    """Raised when ``call()`` is given a tool name a ToolProvider doesn't
    implement. Belt-and-suspenders alongside the Tool Rail's DENY verdict
    — a ToolProvider should never silently no-op on a bad name. Shared
    across every ToolProvider implementation so callers only need to
    catch one exception type regardless of which Business's provider ran.
    """


class ToolProvider(Protocol):
    def call(self, name: str, arguments: dict[str, Any]) -> Any: ...
