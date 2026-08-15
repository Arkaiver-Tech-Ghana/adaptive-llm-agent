"""The only real SessionStore implementation for v1: process-lifetime,
dict-backed, no persistence. Matches the stub's existing framing in
session/base.py — a real (e.g. Redis/Postgres-backed) SessionStore is a
later concern, not required to prove the interface is swappable.
"""

from adaptive_agent.session.base import ConfirmationRequest


class InMemorySessionStore:
    """Implements SessionStore."""

    def __init__(self) -> None:
        self._history: dict[str, list[dict[str, str]]] = {}
        self._pending_confirmations: dict[str, ConfirmationRequest | None] = {}

    def get_history(self, session_key: str) -> list[dict[str, str]]:
        return self._history.get(session_key, [])

    def append(self, session_key: str, role: str, content: str) -> None:
        self._history.setdefault(session_key, []).append({"role": role, "content": content})

    def get_pending_confirmation(self, session_key: str) -> ConfirmationRequest | None:
        return self._pending_confirmations.get(session_key)

    def set_pending_confirmation(
        self, session_key: str, request: ConfirmationRequest | None
    ) -> None:
        self._pending_confirmations[session_key] = request
