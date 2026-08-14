"""The pluggable Session Store axis — stub. Not wired into the Agent Core
Day 1; the CLI keeps an in-process history list instead (see
interfaces/cli.py).

Session is keyed by frontend-type + Customer identity per docs/adr/0002 —
never shared across frontend adapters, even for the same Customer. This
Protocol exists now so a real SessionStore slots in on Day 2 without
touching agent_core.py or the CLI harness.
"""

from typing import Protocol


class SessionStore(Protocol):
    def get_history(self, session_key: str) -> list[dict[str, str]]: ...
    def append(self, session_key: str, role: str, content: str) -> None: ...
