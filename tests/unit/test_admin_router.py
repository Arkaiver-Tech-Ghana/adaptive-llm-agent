from pathlib import Path

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adaptive_agent.admin.auth import hash_password
from adaptive_agent.admin.base import AdminRole, AdminUser
from adaptive_agent.admin.interface_layer import AdminInterfaceLayer
from adaptive_agent.admin.sqlite_store import SqliteAdminStore
from adaptive_agent.interfaces.admin.router import build_admin_router

_CONFIG = {
    "business_id": "kampuscrave",
    "display_name": "KampusCrave",
    "llm": {"provider": "google", "model": "gemini-flash-lite-latest"},
    "context": {"directory": "context"},
    "business_logic": {"persona": "Original persona.", "scope_instructions": "Original scope."},
    "tools": [],
    "storage": {"backend": "sqlite"},
}

_OTHER_CONFIG = {**_CONFIG, "business_id": "hotel", "display_name": "Hotel"}


@pytest.fixture(autouse=True)
def _admin_jwt_secret(monkeypatch):
    monkeypatch.setenv("ADMIN_JWT_SECRET", "test-secret")


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    businesses_dir = tmp_path / "businesses"
    for config in (_CONFIG, _OTHER_CONFIG):
        business_dir = businesses_dir / config["business_id"]
        business_dir.mkdir(parents=True)
        (business_dir / "business.yaml").write_text(yaml.safe_dump(config))

    session_db_dir = tmp_path / "data"
    admin_store = SqliteAdminStore(session_db_dir / "admin.sqlite3")
    admin_store.upsert_user(
        AdminUser(
            email="owner@kc.test",
            password_hash=hash_password("pw"),
            role=AdminRole.OWNER,
            business_id="kampuscrave",
        )
    )
    admin_store.upsert_user(
        AdminUser(
            email="owner@hotel.test",
            password_hash=hash_password("pw"),
            role=AdminRole.OWNER,
            business_id="hotel",
        )
    )
    admin_store.upsert_user(
        AdminUser(
            email="operator@platform.test",
            password_hash=hash_password("pw"),
            role=AdminRole.PLATFORM_OPERATOR,
            business_id=None,
        )
    )

    admin_interface_layer = AdminInterfaceLayer(admin_store)
    app = FastAPI()
    app.include_router(
        build_admin_router(
            admin_interface_layer=admin_interface_layer,
            admin_store=admin_store,
            businesses_dir=businesses_dir,
            session_db_dir=session_db_dir,
        )
    )
    return TestClient(app)


def _login(client: TestClient, email: str, password: str = "pw") -> str:
    response = client.post("/admin/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_login_rejects_wrong_password(client):
    response = client.post(
        "/admin/api/v1/auth/login", json={"email": "owner@kc.test", "password": "wrong"}
    )
    assert response.status_code == 401


def test_login_then_get_config(client):
    token = _login(client, "owner@kc.test")
    response = client.get(
        "/admin/api/v1/businesses/kampuscrave/config", headers=_auth_headers(token)
    )
    assert response.status_code == 200
    assert response.json()["business_logic"]["persona"] == "Original persona."


def test_get_config_without_token_is_401(client):
    response = client.get("/admin/api/v1/businesses/kampuscrave/config")
    assert response.status_code == 401


def test_owner_cannot_read_another_businesss_config(client):
    token = _login(client, "owner@hotel.test")
    response = client.get(
        "/admin/api/v1/businesses/kampuscrave/config", headers=_auth_headers(token)
    )
    assert response.status_code == 403


def test_platform_operator_cannot_write_config_owner_only(client):
    token = _login(client, "operator@platform.test")
    response = client.patch(
        "/admin/api/v1/businesses/hotel/config",
        json={"business_logic": {"persona": "New."}},
        headers=_auth_headers(token),
    )
    assert response.status_code == 403


def test_patch_config_updates_persona_and_leaves_it_persisted(client):
    token = _login(client, "owner@kc.test")
    response = client.patch(
        "/admin/api/v1/businesses/kampuscrave/config",
        json={"business_logic": {"persona": "Updated persona."}},
        headers=_auth_headers(token),
    )
    assert response.status_code == 200
    assert response.json()["business_logic"]["persona"] == "Updated persona."

    reread = client.get(
        "/admin/api/v1/businesses/kampuscrave/config", headers=_auth_headers(token)
    )
    assert reread.json()["business_logic"]["persona"] == "Updated persona."


def test_menu_item_create_list_update(client):
    token = _login(client, "owner@kc.test")
    headers = _auth_headers(token)

    create = client.post(
        "/admin/api/v1/businesses/kampuscrave/menu-items",
        json={"name": "Fries", "category": "sides", "price": 2.5, "stock_quantity": 20},
        headers=headers,
    )
    assert create.status_code == 201

    duplicate = client.post(
        "/admin/api/v1/businesses/kampuscrave/menu-items",
        json={"name": "Fries", "category": "sides", "price": 2.5, "stock_quantity": 20},
        headers=headers,
    )
    assert duplicate.status_code == 409

    listing = client.get("/admin/api/v1/businesses/kampuscrave/menu-items", headers=headers)
    assert [item["name"] for item in listing.json()] == ["Fries"]

    updated = client.patch(
        "/admin/api/v1/businesses/kampuscrave/menu-items/Fries",
        json={"price": 3.0},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["price"] == 3.0


def test_menu_item_delete_requires_confirmation_round_trip(client):
    token = _login(client, "owner@kc.test")
    headers = _auth_headers(token)
    client.post(
        "/admin/api/v1/businesses/kampuscrave/menu-items",
        json={"name": "Fries", "category": "sides", "price": 2.5, "stock_quantity": 20},
        headers=headers,
    )

    first = client.delete("/admin/api/v1/businesses/kampuscrave/menu-items/Fries", headers=headers)
    assert first.status_code == 200
    assert first.json()["status"] == "confirmation_required"
    confirm_token = first.json()["confirm_token"]

    # Still present — nothing executed on the first call.
    listing = client.get("/admin/api/v1/businesses/kampuscrave/menu-items", headers=headers)
    assert len(listing.json()) == 1

    second = client.delete(
        "/admin/api/v1/businesses/kampuscrave/menu-items/Fries",
        params={"confirm_token": confirm_token},
        headers=headers,
    )
    assert second.status_code == 200
    assert second.json()["status"] == "deleted"

    listing_after = client.get("/admin/api/v1/businesses/kampuscrave/menu-items", headers=headers)
    assert listing_after.json() == []


def test_menu_item_delete_rejects_bad_confirm_token(client):
    token = _login(client, "owner@kc.test")
    headers = _auth_headers(token)
    client.post(
        "/admin/api/v1/businesses/kampuscrave/menu-items",
        json={"name": "Fries", "category": "sides", "price": 2.5, "stock_quantity": 20},
        headers=headers,
    )

    response = client.delete(
        "/admin/api/v1/businesses/kampuscrave/menu-items/Fries",
        params={"confirm_token": "made-up"},
        headers=headers,
    )
    assert response.status_code == 400


def test_room_create_and_delete(client):
    token = _login(client, "owner@hotel.test")
    headers = _auth_headers(token)

    create = client.post(
        "/admin/api/v1/businesses/hotel/rooms",
        json={"name": "Deluxe King", "room_type": "deluxe", "price_per_night": 120.0, "availability_count": 3},
        headers=headers,
    )
    assert create.status_code == 201

    first_delete = client.delete("/admin/api/v1/businesses/hotel/rooms/Deluxe King", headers=headers)
    confirm_token = first_delete.json()["confirm_token"]
    second_delete = client.delete(
        "/admin/api/v1/businesses/hotel/rooms/Deluxe King",
        params={"confirm_token": confirm_token},
        headers=headers,
    )
    assert second_delete.json()["status"] == "deleted"


def test_audit_log_records_writes(client):
    token = _login(client, "owner@kc.test")
    headers = _auth_headers(token)
    client.post(
        "/admin/api/v1/businesses/kampuscrave/menu-items",
        json={"name": "Fries", "category": "sides", "price": 2.5, "stock_quantity": 20},
        headers=headers,
    )

    response = client.get("/admin/api/v1/businesses/kampuscrave/audit-log", headers=headers)
    assert response.status_code == 200
    actions = [entry["action"] for entry in response.json()]
    assert "menu_item.create" in actions
