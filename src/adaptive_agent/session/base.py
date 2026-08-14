"""The pluggable Session Store axis — stub. Not wired into the Agent Core
Day 1; the CLI keeps an in-process history list instead (see
interfaces/cli.py).

Session is keyed by frontend-type + Customer identity per docs/adr/0002 —
never shared across frontend adapters, even for the same Customer. This
Protocol exists now so a real SessionStore slots in on Day 2 without
touching agent_core.py or the CLI harness.

``get_history``/``append`` keep their Day 1 signatures unchanged:
intermediate tool-call/tool-result messages are never persisted to
history in this design, only final natural-language turns are. The
pending Tool Rail Confirmation Request (CONTEXT.md) lives alongside
history in the Session, via the two methods added below.
"""

from typing import Protocol

from pydantic import BaseModel

from adaptive_agent.llm.tool_types import ToolCall


class ConfirmationRequest(BaseModel):
    tool_call: ToolCall


class SessionStore(Protocol):
    def get_history(self, session_key: str) -> list[dict[str, str]]: ...
    def append(self, session_key: str, role: str, content: str) -> None: ...
    def get_pending_confirmation(self, session_key: str) -> ConfirmationRequest | None: ...
    def set_pending_confirmation(
        self, session_key: str, request: ConfirmationRequest | None
    ) -> None: ...
