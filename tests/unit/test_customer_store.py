from pathlib import Path

from adaptive_agent.customers.sqlite_store import SqliteCustomerStore


def _store(tmp_path: Path, **kwargs) -> SqliteCustomerStore:
    return SqliteCustomerStore(tmp_path / "customers.sqlite3", **kwargs)


def test_first_visit_sets_first_seen_equal_to_last_seen(tmp_path):
    now = [1_000_000.0]
    store = _store(tmp_path, now_fn=lambda: now[0])

    store.record_visit("2348012345678")

    row = store._conn.execute(
        "SELECT first_seen, last_seen FROM customers WHERE customer_id = ?",
        ("2348012345678",),
    ).fetchone()
    assert row[0] == row[1] == 1_000_000.0


def test_second_visit_advances_last_seen_but_keeps_first_seen(tmp_path):
    now = [1_000_000.0]
    store = _store(tmp_path, now_fn=lambda: now[0])

    store.record_visit("2348012345678")
    now[0] += 500
    store.record_visit("2348012345678")

    row = store._conn.execute(
        "SELECT first_seen, last_seen FROM customers WHERE customer_id = ?",
        ("2348012345678",),
    ).fetchone()
    assert row[0] == 1_000_000.0
    assert row[1] == 1_000_500.0


def test_persists_across_instances(tmp_path):
    db_path = tmp_path / "customers.sqlite3"
    SqliteCustomerStore(db_path, now_fn=lambda: 1_000_000.0).record_visit("local")

    second = SqliteCustomerStore(db_path)
    row = second._conn.execute(
        "SELECT customer_id FROM customers WHERE customer_id = ?", ("local",)
    ).fetchone()
    assert row is not None
