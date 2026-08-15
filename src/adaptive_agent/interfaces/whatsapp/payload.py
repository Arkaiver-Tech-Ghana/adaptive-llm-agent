"""Reduces WhatsApp Cloud API's inbound webhook JSON to one flat shape,
``ParsedWhatsAppMessage``, so ``conversation.py``'s existing
``parse_confirmation_reply`` needs zero changes: a plain-text message and a
quick-reply button tap both become plain text here.

Customer identity is BSUID-preferred: Meta's Business-Scoped User ID
rollout is live (``contacts[].user_id``, since April 2026), and ``wa_id``/
``from`` (the phone number) can be omitted once a Customer sets a WhatsApp
Username. Falling back to ``from`` covers Customers who haven't set one.
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
        customer_id = contact.get("user_id") or message.get("from")
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
