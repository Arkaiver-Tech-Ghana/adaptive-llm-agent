"""The hotel Business's concrete Tool backend for v1.

Seeds a tiny in-memory room inventory and implements two Tools:
``check_room_availability`` (read) and ``book_room`` (write, gated behind
a Confirmation by the Tool Rail per each Business Config's
``requires_confirmation``). Tool names are a shared contract with the
hotel's ``business.yaml`` (a sibling branch) — keep them exactly
``check_room_availability`` / ``book_room``.

This is a demo booking model, not a real one: availability is a static
per-room-type count, not tracked per date range. Good enough to prove the
Tool Rail confirmation flow end to end without building a real booking
engine.
"""

import uuid
from typing import Any


class UnknownToolError(Exception):
    """Raised when ``call()`` is given a tool name this provider doesn't
    implement. Belt-and-suspenders alongside the Tool Rail's DENY verdict
    — this provider should never silently no-op on a bad name.
    """


class InMemoryToolProvider:
    """Implements ToolProvider."""

    def __init__(self) -> None:
        # Seed inventory: room_type -> {nightly_rate, total_rooms}.
        self.rooms: dict[str, dict[str, Any]] = {
            "standard": {"nightly_rate": 80.0, "total_rooms": 5},
            "deluxe": {"nightly_rate": 130.0, "total_rooms": 3},
            "suite": {"nightly_rate": 220.0, "total_rooms": 1},
        }
        # Publicly readable so tests / the eventual CLI can inspect bookings.
        self.bookings: list[dict[str, Any]] = []

    def call(self, name: str, arguments: dict[str, Any]) -> Any:
        if name == "check_room_availability":
            return self._check_room_availability(arguments)
        if name == "book_room":
            return self._book_room(arguments)
        raise UnknownToolError(f"Unknown tool: {name!r}")

    def _check_room_availability(self, arguments: dict[str, Any]) -> dict[str, Any]:
        room_type = arguments["room_type"]
        check_in = arguments["check_in"]
        check_out = arguments["check_out"]
        room = self.rooms.get(room_type)
        if room is None:
            # Unknown room type is a normal "no" answer, not an error — the
            # hotel simply doesn't offer it. Read Tools don't raise on bad
            # arguments, only call() raises, and only for unknown tool names.
            return {
                "available": False,
                "room_type": room_type,
                "reason": f"No such room type: {room_type!r}",
            }
        return {
            "available": True,
            "room_type": room_type,
            "check_in": check_in,
            "check_out": check_out,
            "nightly_rate": room["nightly_rate"],
            "rooms_available": room["total_rooms"],
        }

    def _book_room(self, arguments: dict[str, Any]) -> dict[str, Any]:
        room_type = arguments["room_type"]
        check_in = arguments["check_in"]
        check_out = arguments["check_out"]
        guest_name = arguments["guest_name"]
        room = self.rooms.get(room_type)
        if room is None:
            # Invalid room type: reject without mutating state. No booking
            # id, nothing appended to self.bookings — a clear "didn't
            # happen" signal rather than silently creating a bad record.
            return {
                "success": False,
                "error": f"No such room type: {room_type!r}",
            }
        booking_id = str(uuid.uuid4())
        booking = {
            "booking_id": booking_id,
            "room_type": room_type,
            "check_in": check_in,
            "check_out": check_out,
            "guest_name": guest_name,
            "nightly_rate": room["nightly_rate"],
        }
        self.bookings.append(booking)
        return {"success": True, **booking}
