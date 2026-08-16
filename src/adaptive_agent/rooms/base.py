"""The storage-agnostic contract for the hotel Business's live room data.

Mirrors menu/base.py exactly — the same shape, one table over. Proves the
repository pattern generalizes across Businesses rather than being a
KampusCrave-only convenience.
"""

from typing import Protocol

from pydantic import BaseModel


class Room(BaseModel):
    name: str
    room_type: str
    price_per_night: float
    availability_count: int


class RoomRepository(Protocol):
    def get_room(self, name: str) -> Room | None: ...
    def list_rooms(self) -> list[Room]: ...
    def seed(self, rooms: list[Room]) -> None: ...  # idempotent
    # Create/update reuse seed([room]) (already an upsert) — this is the
    # one write op seed can't express. Returns whether a row was actually
    # removed, so the Admin CRUD router can 404 on an already-gone room.
    def delete_room(self, name: str) -> bool: ...
