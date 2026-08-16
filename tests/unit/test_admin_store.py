from pathlib import Path

from adaptive_agent.admin.base import AdminAuditLogEntry, AdminRole, AdminUser
from adaptive_agent.admin.sqlite_store import SqliteAdminStore


def _store(tmp_path: Path) -> SqliteAdminStore:
    return SqliteAdminStore(tmp_path / "admin.sqlite3")


def test_get_user_by_email_is_none_for_unknown_email(tmp_path):
    store = _store(tmp_path)
    assert store.get_user_by_email("nobody@example.com") is None


def test_upsert_then_get_user_round_trips(tmp_path):
    store = _store(tmp_path)
    user = AdminUser(
        email="owner@kampuscrave.test", password_hash="hash", role=AdminRole.OWNER, business_id="kampuscrave"
    )
    store.upsert_user(user)
    assert store.get_user_by_email("owner@kampuscrave.test") == user


def test_upsert_is_safe_to_rerun_and_overwrites_changed_fields(tmp_path):
    store = _store(tmp_path)
    store.upsert_user(
        AdminUser(email="a@b.test", password_hash="old", role=AdminRole.STAFF, business_id="kampuscrave")
    )
    store.upsert_user(
        AdminUser(email="a@b.test", password_hash="new", role=AdminRole.OWNER, business_id="hotel")
    )

    user = store.get_user_by_email("a@b.test")
    assert user.password_hash == "new"
    assert user.role == AdminRole.OWNER
    assert user.business_id == "hotel"


def test_platform_operator_has_no_business_id(tmp_path):
    store = _store(tmp_path)
    user = AdminUser(email="ops@arkaiver.test", password_hash="hash", role=AdminRole.PLATFORM_OPERATOR)
    store.upsert_user(user)
    assert store.get_user_by_email("ops@arkaiver.test").business_id is None


def test_list_users_for_business_only_returns_that_businesss_users(tmp_path):
    store = _store(tmp_path)
    store.upsert_user(
        AdminUser(email="a@kc.test", password_hash="h", role=AdminRole.OWNER, business_id="kampuscrave")
    )
    store.upsert_user(
        AdminUser(email="b@hotel.test", password_hash="h", role=AdminRole.OWNER, business_id="hotel")
    )

    assert {u.email for u in store.list_users_for_business("kampuscrave")} == {"a@kc.test"}


def test_persists_across_instances(tmp_path):
    db_path = tmp_path / "admin.sqlite3"
    user = AdminUser(email="a@b.test", password_hash="h", role=AdminRole.OWNER, business_id="kampuscrave")
    SqliteAdminStore(db_path).upsert_user(user)

    second = SqliteAdminStore(db_path)
    assert second.get_user_by_email("a@b.test") == user


def test_append_audit_log_then_list_returns_it_with_an_assigned_id(tmp_path):
    store = _store(tmp_path)
    store.append_audit_log(
        AdminAuditLogEntry(
            actor_email="owner@kampuscrave.test",
            business_id="kampuscrave",
            action="menu_item.delete",
            before='{"name": "Fries"}',
            after=None,
            timestamp=1000.0,
        )
    )

    entries = store.list_audit_log("kampuscrave")
    assert len(entries) == 1
    assert entries[0].id is not None
    assert entries[0].action == "menu_item.delete"


def test_list_audit_log_with_none_returns_every_businesss_entries(tmp_path):
    store = _store(tmp_path)
    store.append_audit_log(
        AdminAuditLogEntry(actor_email="a", business_id="kampuscrave", action="x", timestamp=1.0)
    )
    store.append_audit_log(
        AdminAuditLogEntry(actor_email="b", business_id="hotel", action="y", timestamp=2.0)
    )

    assert {e.business_id for e in store.list_audit_log(None)} == {"kampuscrave", "hotel"}


def test_list_audit_log_scoped_to_one_business_excludes_others(tmp_path):
    store = _store(tmp_path)
    store.append_audit_log(
        AdminAuditLogEntry(actor_email="a", business_id="kampuscrave", action="x", timestamp=1.0)
    )
    store.append_audit_log(
        AdminAuditLogEntry(actor_email="b", business_id="hotel", action="y", timestamp=2.0)
    )

    entries = store.list_audit_log("kampuscrave")
    assert [e.business_id for e in entries] == ["kampuscrave"]
