"""Reduces WhatsApp Cloud API's inbound webhook JSON to one flat shape,
``ParsedWhatsAppMessage``, so ``conversation.py``'s existing
``parse_confirmation_reply`` needs zero changes: a plain-text message and a
quick-reply button tap both become plain text here.

Customer identity is normally BSUID-preferred: Meta's Business-Scoped User
ID rollout is live (``contacts[].user_id``, since April 2026), and
``wa_id``/``from`` (the phone number) can be omitted once a Customer sets a
WhatsApp Username. TEMPORARY: this dev-mode app's test-recipient allow-list
doesn't recognize the BSUID as the same tester registered by phone number
(Graph API replies to a BSUID `to` with #131030 "Recipient phone number not
in allowed list" even though the wa_id is allow-listed) — so for now
``wa_id``/``from`` is tried first and the BSUID is the fallback, flipped
from the intended preference. Flip back to BSUID-first once this app is
published (the allow-list only applies in dev mode) or Meta's allow-list
recognizes BSUIDs.
"""

from typing import Any

from pydantic import BaseModel


class ParsedWhatsAppMessage(BaseModel):
    phone_number_id: str
    customer_id: str
    message_id: str
    text: str


def _extract_text(message: dict[str, Any]) -> str | None:
    message_type = message.get("type")
    if message_type == "text":
        return message.get("text", {}).get("body")
    if message_type == "interactive":
        interactive = message.get("interactive", {})
        if interactive.get("type") == "button_reply":
            # "Yes"/"No" button titles, already matched by conversation.py's
            # _YES_REPLIES/_NO_REPLIES after lowercasing.
            return interactive.get("button_reply", {}).get("title")
    return None


def parse_inbound_message(raw_json: dict[str, Any]) -> ParsedWhatsAppMessage | None:
    """Returns None for anything that isn't a routable inbound Customer
    message: malformed payloads, status-update webhooks (no ``messages``
    key), and unsupported message types (image/audio/location/etc.)."""
    try:
        value = raw_json["entry"][0]["changes"][0]["value"]
        phone_number_id = value["metadata"]["phone_number_id"]

        messages = value.get("messages")
        if not messages:
            return None
        message = messages[0]

        text = _extract_text(message)
        if text is None:
            return None

        contacts = value.get("contacts") or []
        contact = contacts[0] if contacts else {}
        customer_id = contact.get("wa_id") or message.get("from") or contact.get("user_id")
        if not customer_id:
            return None

        return ParsedWhatsAppMessage(
            phone_number_id=phone_number_id,
            customer_id=customer_id,
            message_id=message["id"],
            text=text,
        )
    except (KeyError, IndexError, TypeError):
        return None
