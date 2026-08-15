from adaptive_agent.interfaces.whatsapp.payload import (
    ParsedWhatsAppMessage,
    parse_inbound_message,
)


def _envelope(value: dict) -> dict:
    return {"entry": [{"id": "waba-1", "changes": [{"value": value, "field": "messages"}]}]}


def test_text_message_with_bsuid_present_prefers_wa_id():
    """TEMPORARY (see payload.py's docstring): wa_id is preferred over the
    BSUID for now, since this dev-mode app's test-recipient allow-list
    doesn't recognize the BSUID for replies. Flip back once that's fixed."""
    value = {
        "metadata": {"phone_number_id": "123456"},
        "contacts": [{"profile": {"name": "Ada"}, "wa_id": "15551234567", "user_id": "bsuid-abc"}],
        "messages": [{"from": "15551234567", "id": "wamid.1", "type": "text", "text": {"body": "hi"}}],
    }

    result = parse_inbound_message(_envelope(value))

    assert result == ParsedWhatsAppMessage(
        phone_number_id="123456", customer_id="15551234567", message_id="wamid.1", text="hi"
    )


def test_customer_id_falls_back_to_bsuid_when_wa_id_and_from_absent():
    value = {
        "metadata": {"phone_number_id": "123456"},
        "contacts": [{"profile": {"name": "Ada"}, "user_id": "bsuid-abc"}],
        "messages": [{"id": "wamid.1", "type": "text", "text": {"body": "hi"}}],
    }

    result = parse_inbound_message(_envelope(value))

    assert result.customer_id == "bsuid-abc"


def test_interactive_button_reply_reduces_to_its_title():
    value = {
        "metadata": {"phone_number_id": "123456"},
        "contacts": [{"wa_id": "15551234567", "user_id": "bsuid-abc"}],
        "messages": [
            {
                "from": "15551234567",
                "id": "wamid.2",
                "type": "interactive",
                "interactive": {
                    "type": "button_reply",
                    "button_reply": {"id": "confirm_yes", "title": "Yes"},
                },
            }
        ],
    }

    result = parse_inbound_message(_envelope(value))

    assert result.text == "Yes"
    assert result.message_id == "wamid.2"


def test_status_update_webhook_with_no_messages_returns_none():
    value = {
        "metadata": {"phone_number_id": "123456"},
        "statuses": [{"id": "wamid.1", "status": "delivered"}],
    }
    assert parse_inbound_message(_envelope(value)) is None


def test_unsupported_message_type_returns_none():
    value = {
        "metadata": {"phone_number_id": "123456"},
        "contacts": [{"wa_id": "15551234567"}],
        "messages": [{"from": "15551234567", "id": "wamid.3", "type": "image", "image": {}}],
    }
    assert parse_inbound_message(_envelope(value)) is None


def test_malformed_payload_returns_none():
    assert parse_inbound_message({"unexpected": "shape"}) is None
    assert parse_inbound_message({}) is None
