import pytest

from adaptive_agent.tools.in_memory_provider import (
    InMemoryToolProvider,
    UnknownToolError,
)


def test_check_room_availability_returns_read_data_without_mutating_bookings():
    provider = InMemoryToolProvider()
    result = provider.call(
        "check_room_availability",
        {"room_type": "deluxe", "check_in": "2026-09-01", "check_out": "2026-09-03"},
    )
    assert result["available"] is True
    assert result["room_type"] == "deluxe"
    assert result["nightly_rate"] == 130.0
    assert provider.bookings == []


def test_check_room_availability_for_unknown_room_type_is_not_available():
    provider = InMemoryToolProvider()
    result = provider.call(
        "check_room_availability",
        {"room_type": "penthouse", "check_in": "2026-09-01", "check_out": "2026-09-03"},
    )
    assert result["available"] is False
    assert provider.bookings == []


def test_book_room_appends_to_bookings_and_returns_confirmation():
    provider = InMemoryToolProvider()
    result = provider.call(
        "book_room",
        {
            "room_type": "suite",
            "check_in": "2026-09-01",
            "check_out": "2026-09-03",
            "guest_name": "Ada Lovelace",
        },
    )
    assert result["success"] is True
    assert "booking_id" in result
    assert result["guest_name"] == "Ada Lovelace"
    assert len(provider.bookings) == 1
    assert provider.bookings[0]["room_type"] == "suite"
    assert provider.bookings[0]["guest_name"] == "Ada Lovelace"


def test_book_room_with_unknown_room_type_fails_without_appending():
    # Decision: an invalid room type is rejected with success=False and no
    # booking record created, rather than raising or silently booking
    # something nonsensical. Unlike an unknown *tool name* (which raises
    # UnknownToolError), a bad *argument* for a known tool is a normal
    # "no" response the caller can relay to the customer.
    provider = InMemoryToolProvider()
    result = provider.call(
        "book_room",
        {
            "room_type": "penthouse",
            "check_in": "2026-09-01",
            "check_out": "2026-09-03",
            "guest_name": "Ada Lovelace",
        },
    )
    assert result["success"] is False
    assert provider.bookings == []


def test_unknown_tool_name_raises_unknown_tool_error():
    provider = InMemoryToolProvider()
    with pytest.raises(UnknownToolError):
        provider.call("cancel_booking", {})
