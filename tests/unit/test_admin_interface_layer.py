from pathlib import Path

import pytest

from adaptive_agent.admin.auth import create_access_token, hash_password
from adaptive_agent.admin.base import AdminRole, AdminUser
from adaptive_agent.admin.interface_layer import (
    AdminAuthError,
    AdminForbiddenError,
    AdminInterfaceLayer,
    InvalidConfirmationTokenError,
)
from adaptive_agent.admin.sqlite_store import SqliteAdminStore


@pytest.fixture(autouse=True)
def _admin_jwt_secret(monkeypatch):
    monkeypatch.setenv("ADMIN_JWT_SECRET", "test-secret")


def _layer_with_users(tmp_path: Path) -> tuple[AdminInterfaceLayer, SqliteAdminStore]:
    store = SqliteAdminStore(tmp_path / "admin.sqlite3")
    store.upsert_user(
        AdminUser(
            email="owner@kc.test",
            password_hash=hash_password("pw"),
            role=AdminRole.OWNER,
            business_id="kampuscrave",
        )
    )
    store.upsert_user(
        AdminUser(
            email="staff@hotel.test",
            password_hash=hash_password("pw"),
            role=AdminRole.STAFF,
            business_id="hotel",
        )
    )
    store.upsert_user(
        AdminUser(
            email="ops@arkaiver.test",
            password_hash=hash_password("pw"),
            role=AdminRole.PLATFORM_OPERATOR,
        )
    )
    return AdminInterfaceLayer(store), store


def _token_for(store: SqliteAdminStore, email: str) -> str:
    return create_access_token(store.get_user_by_email(email))


def test_owner_authorized_for_own_business(tmp_path):
    layer, store = _layer_with_users(tmp_path)
    token = _token_for(store, "owner@kc.test")

    user = layer.authorize(token, "kampuscrave", {AdminRole.OWNER, AdminRole.STAFF})
    assert user.email == "owner@kc.test"


def test_staff_forbidden_from_another_business(tmp_path):
    layer, store = _layer_with_users(tmp_path)
    token = _token_for(store, "staff@hotel.test")

    with pytest.raises(AdminForbiddenError):
        layer.authorize(token, "kampuscrave", {AdminRole.OWNER, AdminRole.STAFF})


def test_staff_forbidden_from_owner_only_action(tmp_path):
    layer, store = _layer_with_users(tmp_path)
    token = _token_for(store, "staff@hotel.test")

    with pytest.raises(AdminForbiddenError):
        layer.authorize(token, "hotel", {AdminRole.OWNER})


def test_platform_operator_allowed_cross_business_when_role_permitted(tmp_path):
    layer, store = _layer_with_users(tmp_path)
    token = _token_for(store, "ops@arkaiver.test")

    user = layer.authorize(token, "kampuscrave", {AdminRole.OWNER, AdminRole.PLATFORM_OPERATOR})
    assert user.email == "ops@arkaiver.test"


def test_platform_operator_forbidden_from_write_route_that_excludes_it(tmp_path):
    layer, store = _layer_with_users(tmp_path)
    token = _token_for(store, "ops@arkaiver.test")

    with pytest.raises(AdminForbiddenError):
        layer.authorize(token, "kampuscrave", {AdminRole.OWNER, AdminRole.STAFF})


def test_authorize_rejects_bad_token(tmp_path):
    layer, _ = _layer_with_users(tmp_path)
    with pytest.raises(AdminAuthError):
        layer.authorize("not-a-real-token", "kampuscrave", {AdminRole.OWNER})


def test_confirmation_round_trip_token_then_resolve(tmp_path):
    layer, _ = _layer_with_users(tmp_path)
    token = layer.request_confirmation("Delete menu item 'Fries' from kampuscrave")
    layer.resolve_confirmation(token)  # doesn't raise


def test_confirmation_token_is_single_use(tmp_path):
    layer, _ = _layer_with_users(tmp_path)
    token = layer.request_confirmation("Delete menu item 'Fries' from kampuscrave")
    layer.resolve_confirmation(token)

    with pytest.raises(InvalidConfirmationTokenError):
        layer.resolve_confirmation(token)


def test_confirmation_rejects_unknown_token(tmp_path):
    layer, _ = _layer_with_users(tmp_path)
    with pytest.raises(InvalidConfirmationTokenError):
        layer.resolve_confirmation("made-up-token")


def test_confirmation_rejects_expired_token(tmp_path):
    store = SqliteAdminStore(tmp_path / "admin.sqlite3")
    fake_now = [1000.0]
    layer = AdminInterfaceLayer(store, now_fn=lambda: fake_now[0])

    token = layer.request_confirmation("Delete menu item 'Fries' from kampuscrave")
    fake_now[0] += 10 * 60  # past the 5-minute TTL

    with pytest.raises(InvalidConfirmationTokenError):
        layer.resolve_confirmation(token)
