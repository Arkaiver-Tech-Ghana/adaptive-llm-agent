"""Outbound replies to WhatsApp Cloud API's Graph API send endpoint.
``to`` is always the BSUID-preferred customer id (payload.py) — the Graph
API's send endpoint accepts either a phone number or a BSUID in ``to``, so
no extra lookup is needed to reply.
"""

import httpx

_GRAPH_API_VERSION = "v21.0"


def _graph_url(phone_number_id: str) -> str:
    return f"https://graph.facebook.com/{_GRAPH_API_VERSION}/{phone_number_id}/messages"


def _post(phone_number_id: str, access_token: str, payload: dict) -> None:
    response = httpx.post(
        _graph_url(phone_number_id),
        headers={"Authorization": f"Bearer {access_token}"},
        json=payload,
        timeout=10.0,
    )
    response.raise_for_status()


def send_text_message(*, phone_number_id: str, to: str, text: str, access_token: str) -> None:
    _post(
        phone_number_id,
        access_token,
        {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text},
        },
    )


def send_confirmation_buttons(
    *, phone_number_id: str, to: str, text: str, access_token: str
) -> None:
    """A real WhatsApp quick-reply button, not a narrated one — this is
    what lets the video show the confirmation flow end to end. Button
    titles are "Yes"/"No", already matched by conversation.py's
    _YES_REPLIES/_NO_REPLIES once payload.py reduces the tap back to text.
    """
    _post(
        phone_number_id,
        access_token,
        {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": text},
                "action": {
                    "buttons": [
                        {"type": "reply", "reply": {"id": "confirm_yes", "title": "Yes"}},
                        {"type": "reply", "reply": {"id": "confirm_no", "title": "No"}},
                    ]
                },
            },
        },
    )
