"""The Interface Layer's request/response contract — the thing living
*between* a Frontend Adapter and ``ConversationRuntime`` (CONTEXT.md's
Interface Layer definition), shared by every Interface-Layer-based
frontend, not just WhatsApp.

``MAX_MESSAGE_LENGTH`` matches Meta's own documented WhatsApp text-message
cap. Meta's UI enforces this client-side only — nothing stops a
malformed/unexpected payload from carrying more — so it's enforced here,
on construction, rather than trusted from the sender. Living on this
shared contract (not just inside the WhatsApp adapter) means any future
Interface-Layer-based frontend inherits the same protection for free. The
CLI harness bypasses the Interface Layer entirely by its pre-existing Day
1 design (see ``interfaces/cli.py``'s docstring) — a known, already-
accepted exception, not something this contract changes.
"""

from typing import Literal

from pydantic import BaseModel, Field

MAX_MESSAGE_LENGTH = 4096


class InboundRequest(BaseModel):
    business_key: str
    session_key: str
    rate_limit_key: str
    message_id: str
    message_text: str = Field(max_length=MAX_MESSAGE_LENGTH)


class OutboundResponse(BaseModel):
    status: Literal["ok", "rate_limited", "duplicate", "unknown_business"]
    text: str | None = None
    # True when a Confirmation Request is now pending for this session —
    # the caller (e.g. the WhatsApp router) uses this to decide whether to
    # send quick-reply buttons instead of a plain text message.
    awaiting_confirmation: bool = False
