import pytest
from pydantic import ValidationError

from adaptive_agent.interface_layer.contract import MAX_MESSAGE_LENGTH, InboundRequest
from adaptive_agent.interface_layer.dedupe import InMemoryDedupeStore
from adaptive_agent.interface_layer.rate_limiter import RateLimiter
from adaptive_agent.interface_layer.service import InterfaceLayer
from tests.unit.fakes import FakeConversationRuntime


def _request(**overrides) -> InboundRequest:
    defaults = {
        "business_key": "hotel-phone-id",
        "session_key": "whatsapp:customer-1",
        "rate_limit_key": "whatsapp:customer-1",
        "message_id": "wamid.1",
        "message_text": "hi",
    }
    defaults.update(overrides)
    return InboundRequest(**defaults)


def test_unknown_business_key_returns_unknown_business_without_raising():
    runtime = FakeConversationRuntime()
    layer = InterfaceLayer(business_registry={"hotel-phone-id": runtime})

    response = layer.process(_request(business_key="ghost-phone-id"))

    assert response.status == "unknown_business"
    assert runtime.calls == []


def test_ok_response_carries_runtimes_reply_text():
    runtime = FakeConversationRuntime(canned_reply="Hello there!")
    layer = InterfaceLayer(business_registry={"hotel-phone-id": runtime})

    response = layer.process(_request())

    assert response.status == "ok"
    assert response.text == "Hello there!"
    assert response.awaiting_confirmation is False


def test_awaiting_confirmation_true_when_a_confirmation_is_pending_after_reply():
    runtime = FakeConversationRuntime(pending_after_reply=object())
    layer = InterfaceLayer(business_registry={"hotel-phone-id": runtime})

    response = layer.process(_request())

    assert response.awaiting_confirmation is True


def test_duplicate_message_id_short_circuits_before_handle_message():
    runtime = FakeConversationRuntime()
    layer = InterfaceLayer(business_registry={"hotel-phone-id": runtime})

    first = layer.process(_request(message_id="wamid.same"))
    second = layer.process(_request(message_id="wamid.same"))

    assert first.status == "ok"
    assert second.status == "duplicate"
    assert len(runtime.calls) == 1


def test_rate_limited_nth_plus_one_call_never_reaches_handle_message():
    runtime = FakeConversationRuntime()
    rate_limiter = RateLimiter(max_per_minute=2)
    layer = InterfaceLayer(
        business_registry={"hotel-phone-id": runtime}, rate_limiter=rate_limiter
    )

    layer.process(_request(message_id="wamid.1"))
    layer.process(_request(message_id="wamid.2"))
    third = layer.process(_request(message_id="wamid.3"))

    assert third.status == "rate_limited"
    assert len(runtime.calls) == 2


def test_dedupe_checked_before_rate_limit_so_a_retry_does_not_burn_budget():
    runtime = FakeConversationRuntime()
    rate_limiter = RateLimiter(max_per_minute=1)
    dedupe_store = InMemoryDedupeStore()
    layer = InterfaceLayer(
        business_registry={"hotel-phone-id": runtime},
        rate_limiter=rate_limiter,
        dedupe_store=dedupe_store,
    )

    layer.process(_request(message_id="wamid.1"))
    # Same message_id retried: caught by dedupe, must not also consume the
    # (already-exhausted) rate-limit budget.
    retry = layer.process(_request(message_id="wamid.1"))
    # A genuinely new message right after: rate limit (not dedupe) is what
    # blocks it, proving the retry above didn't get counted as a rate-limit hit.
    fresh = layer.process(_request(message_id="wamid.2"))

    assert retry.status == "duplicate"
    assert fresh.status == "rate_limited"
    assert len(runtime.calls) == 1


def test_oversized_message_text_fails_construction_before_process_is_reachable():
    with pytest.raises(ValidationError):
        _request(message_text="x" * (MAX_MESSAGE_LENGTH + 1))
