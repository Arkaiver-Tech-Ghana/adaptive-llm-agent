from pathlib import Path

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adaptive_agent.admin.auth import create_access_token, hash_password
from adaptive_agent.admin.base import AdminRole, AdminUser
from adaptive_agent.admin.interface_layer import AdminInterfaceLayer
from adaptive_agent.admin.sqlite_store import SqliteAdminStore
from adaptive_agent.interfaces.admin.entities_router import build_entities_router

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

    admin_interface_layer = AdminInterfaceLayer(admin_store)
    app = FastAPI()
    app.include_router(
        build_entities_router(
            admin_interface_layer=admin_interface_layer,
            admin_store=admin_store,
            businesses_dir=businesses_dir,
            session_db_dir=session_db_dir,
        )
    )
    return TestClient(app)


def _login_headers(email: str) -> dict:
    # Builds a token directly rather than hitting a /login route — that
    # route lives in interfaces/admin/router.py, not this one. authorize()
    # looks up role/business_id fresh from the store by the token's email
    # claim, so only email needs to match a fixture-registered user.
    token = create_access_token(AdminUser(email=email, password_hash="unused", role=AdminRole.OWNER))
    return {"Authorization": f"Bearer {token}"}


_NOTES_TABLE = {
    "table_name": "notes",
    "display_name": "Notes",
    "columns": [{"name": "title", "type": "text", "required": True}],
    "tool_linked": None,
}


def test_create_list_table_round_trip(client):
    headers = _login_headers("owner@kc.test")

    create = client.post(
        "/admin/api/v1/businesses/kampuscrave/tables", json=_NOTES_TABLE, headers=headers
    )
    assert create.status_code == 201

    listing = client.get("/admin/api/v1/businesses/kampuscrave/tables", headers=headers)
    assert [t["table_name"] for t in listing.json()] == ["notes"]


def test_owner_cannot_manage_another_businesss_tables(client):
    headers = _login_headers("owner@hotel.test")
    response = client.post(
        "/admin/api/v1/businesses/kampuscrave/tables", json=_NOTES_TABLE, headers=headers
    )
    assert response.status_code == 403


def test_create_table_rejects_duplicate_name(client):
    headers = _login_headers("owner@kc.test")
    client.post("/admin/api/v1/businesses/kampuscrave/tables", json=_NOTES_TABLE, headers=headers)

    duplicate = client.post(
        "/admin/api/v1/businesses/kampuscrave/tables", json=_NOTES_TABLE, headers=headers
    )
    assert duplicate.status_code == 409


def test_row_create_list_update_round_trip(client):
    headers = _login_headers("owner@kc.test")
    client.post("/admin/api/v1/businesses/kampuscrave/tables", json=_NOTES_TABLE, headers=headers)

    created = client.post(
        "/admin/api/v1/businesses/kampuscrave/tables/notes/rows",
        json={"title": "First"},
        headers=headers,
    )
    assert created.status_code == 201
    row_id = created.json()["id"]

    listing = client.get(
        "/admin/api/v1/businesses/kampuscrave/tables/notes/rows", headers=headers
    )
    assert [r["title"] for r in listing.json()] == ["First"]

    updated = client.patch(
        f"/admin/api/v1/businesses/kampuscrave/tables/notes/rows/{row_id}",
        json={"title": "Updated"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Updated"
    assert updated.json()["id"] == row_id


def test_row_delete_requires_confirmation_round_trip(client):
    headers = _login_headers("owner@kc.test")
    client.post("/admin/api/v1/businesses/kampuscrave/tables", json=_NOTES_TABLE, headers=headers)
    created = client.post(
        "/admin/api/v1/businesses/kampuscrave/tables/notes/rows",
        json={"title": "First"},
        headers=headers,
    )
    row_id = created.json()["id"]

    first = client.delete(
        f"/admin/api/v1/businesses/kampuscrave/tables/notes/rows/{row_id}", headers=headers
    )
    assert first.json()["status"] == "confirmation_required"
    confirm_token = first.json()["confirm_token"]

    second = client.delete(
        f"/admin/api/v1/businesses/kampuscrave/tables/notes/rows/{row_id}",
        params={"confirm_token": confirm_token},
        headers=headers,
    )
    assert second.json()["status"] == "deleted"

    listing = client.get(
        "/admin/api/v1/businesses/kampuscrave/tables/notes/rows", headers=headers
    )
    assert listing.json() == []


def test_table_delete_requires_confirmation_round_trip(client):
    headers = _login_headers("owner@kc.test")
    client.post("/admin/api/v1/businesses/kampuscrave/tables", json=_NOTES_TABLE, headers=headers)

    first = client.delete(
        "/admin/api/v1/businesses/kampuscrave/tables/notes", headers=headers
    )
    assert first.json()["status"] == "confirmation_required"
    confirm_token = first.json()["confirm_token"]

    second = client.delete(
        "/admin/api/v1/businesses/kampuscrave/tables/notes",
        params={"confirm_token": confirm_token},
        headers=headers,
    )
    assert second.json()["status"] == "deleted"

    listing = client.get("/admin/api/v1/businesses/kampuscrave/tables", headers=headers)
    assert listing.json() == []


def test_row_operations_404_on_unknown_table(client):
    headers = _login_headers("owner@kc.test")
    response = client.get(
        "/admin/api/v1/businesses/kampuscrave/tables/ghost/rows", headers=headers
    )
    assert response.status_code == 404


def test_add_rename_and_list_column_round_trip(client):
    headers = _login_headers("owner@kc.test")
    client.post("/admin/api/v1/businesses/kampuscrave/tables", json=_NOTES_TABLE, headers=headers)

    added = client.post(
        "/admin/api/v1/businesses/kampuscrave/tables/notes/columns",
        json={"name": "tag", "type": "text", "required": False},
        headers=headers,
    )
    assert added.status_code == 201
    assert {c["name"] for c in added.json()["columns"]} == {"title", "tag"}

    renamed = client.patch(
        "/admin/api/v1/businesses/kampuscrave/tables/notes/columns/tag",
        json={"name": "label"},
        headers=headers,
    )
    assert renamed.status_code == 200
    assert {c["name"] for c in renamed.json()["columns"]} == {"title", "label"}

    listing = client.get("/admin/api/v1/businesses/kampuscrave/tables", headers=headers)
    assert {c["name"] for c in listing.json()[0]["columns"]} == {"title", "label"}


def test_add_column_rejects_duplicate_name(client):
    headers = _login_headers("owner@kc.test")
    client.post("/admin/api/v1/businesses/kampuscrave/tables", json=_NOTES_TABLE, headers=headers)

    response = client.post(
        "/admin/api/v1/businesses/kampuscrave/tables/notes/columns",
        json={"name": "title", "type": "text", "required": False},
        headers=headers,
    )
    assert response.status_code == 409


def test_column_delete_requires_confirmation_round_trip(client):
    headers = _login_headers("owner@kc.test")
    client.post("/admin/api/v1/businesses/kampuscrave/tables", json=_NOTES_TABLE, headers=headers)
    client.post(
        "/admin/api/v1/businesses/kampuscrave/tables/notes/columns",
        json={"name": "tag", "type": "text", "required": False},
        headers=headers,
    )

    first = client.delete(
        "/admin/api/v1/businesses/kampuscrave/tables/notes/columns/tag", headers=headers
    )
    assert first.json()["status"] == "confirmation_required"
    confirm_token = first.json()["confirm_token"]

    second = client.delete(
        "/admin/api/v1/businesses/kampuscrave/tables/notes/columns/tag",
        params={"confirm_token": confirm_token},
        headers=headers,
    )
    assert second.json()["status"] == "deleted"

    listing = client.get("/admin/api/v1/businesses/kampuscrave/tables", headers=headers)
    assert {c["name"] for c in listing.json()[0]["columns"]} == {"title"}


def test_column_operations_404_on_unknown_column(client):
    headers = _login_headers("owner@kc.test")
    client.post("/admin/api/v1/businesses/kampuscrave/tables", json=_NOTES_TABLE, headers=headers)

    rename = client.patch(
        "/admin/api/v1/businesses/kampuscrave/tables/notes/columns/ghost",
        json={"name": "new_name"},
        headers=headers,
    )
    assert rename.status_code == 404

    delete = client.delete(
        "/admin/api/v1/businesses/kampuscrave/tables/notes/columns/ghost", headers=headers
    )
    assert delete.status_code == 404
