"""The pluggable Input/Output Rail axis.

``RailChecker`` is a real Protocol (unlike the Tool Rail/Data Rail, which are
plain functions) because it wraps a genuinely swappable external dependency
(NeMo Guardrails today) and needs a fake for offline unit tests. The Agent
Core never depends on NeMo directly — only on this Protocol.
"""

from typing import Protocol

from pydantic import BaseModel


class RailVerdict(BaseModel):
    """The outcome of one Input Rail or Output Rail check.

    ``text`` carries the message forward regardless of the verdict: when
    ``allowed`` is True it's the (possibly rewritten) original text; when
    False it's the refusal/replacement text the Customer should see instead.
    """

    allowed: bool
    text: str
    activated_rail: str | None = None


class RailChecker(Protocol):
    def check_input(self, message: str) -> RailVerdict: ...

    def check_output(self, response_text: str) -> RailVerdict: ...
