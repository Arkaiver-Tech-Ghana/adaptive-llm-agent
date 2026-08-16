from pathlib import Path

import pytest

from adaptive_agent.rooms.base import Room
from adaptive_agent.rooms.sqlite_repository import (
    InvalidRoomTableConfigError,
    SqliteRoomRepository,
)


def _store(tmp_path: Path) -> SqliteRoomRepository:
    return SqliteRoomRepository(tmp_path / "rooms.sqlite3")


def test_get_room_is_none_for_unknown_name(tmp_path):
    repo = _store(tmp_path)
    assert repo.get_room("Deluxe King") is None


def test_seed_then_get_room_round_trips(tmp_path):
    repo = _store(tmp_path)
    room = Room(name="Deluxe King", room_type="deluxe", price_per_night=120.0, availability_count=3)
    repo.seed([room])
    assert repo.get_room("Deluxe King") == room


def test_list_rooms_returns_every_seeded_room(tmp_path):
    repo = _store(tmp_path)
    rooms = [
        Room(name="Deluxe King", room_type="deluxe", price_per_night=120.0, availability_count=3),
        Room(name="Standard Twin", room_type="standard", price_per_night=80.0, availability_count=5),
    ]
    repo.seed(rooms)
    assert {room.name for room in repo.list_rooms()} == {"Deluxe King", "Standard Twin"}


def test_seed_is_safe_to_rerun_and_overwrites_changed_fields(tmp_path):
    repo = _store(tmp_path)
    repo.seed([Room(name="Standard Twin", room_type="standard", price_per_night=80.0, availability_count=5)])
    repo.seed([Room(name="Standard Twin", room_type="standard", price_per_night=90.0, availability_count=2)])

    room = repo.get_room("Standard Twin")
    assert room.price_per_night == 90.0
    assert room.availability_count == 2
    assert len(repo.list_rooms()) == 1


def test_persists_across_instances(tmp_path):
    db_path = tmp_path / "rooms.sqlite3"
    room = Room(name="Standard Twin", room_type="standard", price_per_night=80.0, availability_count=5)
    SqliteRoomRepository(db_path).seed([room])

    second = SqliteRoomRepository(db_path)
    assert second.get_room("Standard Twin") == room


def test_custom_table_and_column_names_round_trip(tmp_path):
    repo = SqliteRoomRepository(
        tmp_path / "rooms.sqlite3",
        table="inventory",
        columns={
            "name": "room_name",
            "room_type": "type",
            "price_per_night": "nightly_rate",
            "availability_count": "qty_free",
        },
    )
    room = Room(name="Standard Twin", room_type="standard", price_per_night=80.0, availability_count=5)
    repo.seed([room])
    assert repo.get_room("Standard Twin") == room


def test_custom_table_is_actually_used_not_the_default(tmp_path):
    db_path = tmp_path / "rooms.sqlite3"
    repo = SqliteRoomRepository(db_path, table="inventory")
    repo.seed([Room(name="Standard Twin", room_type="standard", price_per_night=80.0, availability_count=5)])

    default_named_repo = SqliteRoomRepository(db_path)  # reads "rooms"
    assert default_named_repo.get_room("Standard Twin") is None


def test_delete_room_removes_it_and_returns_true(tmp_path):
    repo = _store(tmp_path)
    repo.seed([Room(name="Standard Twin", room_type="standard", price_per_night=80.0, availability_count=5)])

    assert repo.delete_room("Standard Twin") is True
    assert repo.get_room("Standard Twin") is None


def test_delete_room_returns_false_for_unknown_name(tmp_path):
    repo = _store(tmp_path)
    assert repo.delete_room("Nonexistent") is False


def test_rejects_table_name_that_is_not_a_valid_identifier(tmp_path):
    with pytest.raises(InvalidRoomTableConfigError):
        SqliteRoomRepository(tmp_path / "rooms.sqlite3", table="rooms; DROP TABLE rooms;--")


def test_rejects_column_name_that_is_not_a_valid_identifier(tmp_path):
    with pytest.raises(InvalidRoomTableConfigError):
        SqliteRoomRepository(
            tmp_path / "rooms.sqlite3",
            columns={
                "name": "name; --",
                "room_type": "room_type",
                "price_per_night": "price_per_night",
                "availability_count": "availability_count",
            },
        )


def test_rejects_columns_missing_a_required_field(tmp_path):
    with pytest.raises(InvalidRoomTableConfigError):
        SqliteRoomRepository(
            tmp_path / "rooms.sqlite3",
            columns={"name": "name", "room_type": "room_type", "price_per_night": "price_per_night"},
        )
