import hashlib
import hmac
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

import adaptive_agent.interfaces.whatsapp.router as router_module
from adaptive_agent.interface_layer.service import InterfaceLayer
from adaptive_agent.interfaces.whatsapp.router import build_router
from tests.unit.fakes import FakeConversationRuntime

_APP_SECRET = "shh-its-a-secret"
_VERIFY_TOKEN = "verify-me"
_ACCESS_TOKEN = "test-access-token"
_PHONE_NUMBER_ID = "123456"


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(_APP_SECRET.encode(), body, hashlib.sha256).hexdigest()


def _text_message_body(*, message_id: str = "wamid.1", text: str = "hi", from_: str = "155501") -> bytes:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": _PHONE_NUMBER_ID},
                            "contacts": [{"wa_id": from_, "user_id": "bsuid-1"}],
                            "messages": [
                                {"from": from_, "id": message_id, "type": "text", "text": {"body": text}}
                            ],
                        }
                    }
                ]
            }
        ]
    }
    return json.dumps(payload).encode()


def _client(runtime, monkeypatch):
    sent = []
    monkeypatch.setattr(
        router_module.outbound,
        "send_text_message",
        lambda **kwargs: sent.append(("text", kwargs)),
    )
    monkeypatch.setattr(
        router_module.outbound,
        "send_confirmation_buttons",
        lambda **kwargs: sent.append(("buttons", kwargs)),
    )

    interface_layer = InterfaceLayer(business_registry={_PHONE_NUMBER_ID: runtime})
    app = FastAPI()
    app.include_router(
        build_router(
            interface_layer=interface_layer,
            verify_token=_VERIFY_TOKEN,
            app_secret=_APP_SECRET,
            access_token=_ACCESS_TOKEN,
        )
    )
    return TestClient(app), sent


def test_get_verify_returns_challenge_on_matching_token(monkeypatch):
    client, _ = _client(FakeConversationRuntime(), monkeypatch)

    response = client.get(
        "/webhook/whatsapp",
        params={"hub.mode": "subscribe", "hub.verify_token": _VERIFY_TOKEN, "hub.challenge": "1234"},
    )

    assert response.status_code == 200
    assert response.text == "1234"


def test_get_verify_returns_403_on_mismatched_token(monkeypatch):
    client, _ = _client(FakeConversationRuntime(), monkeypatch)

    response = client.get(
        "/webhook/whatsapp",
        params={"hub.mode": "subscribe", "hub.verify_token": "wrong-token", "hub.challenge": "1234"},
    )

    assert response.status_code == 403


def test_post_valid_signature_and_text_sends_reply_once(monkeypatch):
    runtime = FakeConversationRuntime(canned_reply="Hello!")
    client, sent = _client(runtime, monkeypatch)
    body = _text_message_body()

    response = client.post(
        "/webhook/whatsapp",
        content=body,
        headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert len(sent) == 1
    kind, kwargs = sent[0]
    assert kind == "text"
    assert kwargs["text"] == "Hello!"
    assert len(runtime.calls) == 1


def test_post_bad_signature_is_rejected_and_never_calls_outbound(monkeypatch):
    runtime = FakeConversationRuntime()
    client, sent = _client(runtime, monkeypatch)
    body = _text_message_body()

    response = client.post(
        "/webhook/whatsapp",
        content=body,
        headers={"X-Hub-Signature-256": "sha256=deadbeef", "Content-Type": "application/json"},
    )

    assert response.status_code == 401
    assert sent == []
    assert runtime.calls == []


def test_post_same_message_id_twice_only_calls_outbound_once(monkeypatch):
    runtime = FakeConversationRuntime(canned_reply="Hello!")
    client, sent = _client(runtime, monkeypatch)
    body = _text_message_body(message_id="wamid.dupe")

    client.post(
        "/webhook/whatsapp",
        content=body,
        headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"},
    )
    client.post(
        "/webhook/whatsapp",
        content=body,
        headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"},
    )

    assert len(sent) == 1
    assert len(runtime.calls) == 1


def test_post_oversized_message_replies_with_fixed_text_and_never_reaches_interface_layer(monkeypatch):
    runtime = FakeConversationRuntime()
    client, sent = _client(runtime, monkeypatch)
    body = _text_message_body(text="x" * 5000)

    response = client.post(
        "/webhook/whatsapp",
        content=body,
        headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert len(sent) == 1
    kind, kwargs = sent[0]
    assert kind == "text"
    assert "too long" in kwargs["text"].lower()
    assert runtime.calls == []


def test_awaiting_confirmation_sends_buttons_instead_of_plain_text(monkeypatch):
    runtime = FakeConversationRuntime(canned_reply="Confirm?", pending_after_reply=object())
    client, sent = _client(runtime, monkeypatch)
    body = _text_message_body()

    client.post(
        "/webhook/whatsapp",
        content=body,
        headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"},
    )

    assert len(sent) == 1
    kind, kwargs = sent[0]
    assert kind == "buttons"
    assert kwargs["text"] == "Confirm?"
