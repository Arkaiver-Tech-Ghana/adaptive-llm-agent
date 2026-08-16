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


def test_signup_creates_business_and_owner_and_logs_in(client):
    response = client.post(
        "/admin/api/v1/auth/signup",
        json={
            "business_id": "acme-cafe",
            "display_name": "Acme Cafe",
            "owner_email": "owner@acme.test",
            "owner_password": "temp-pw",
        },
    )
    assert response.status_code == 201
    token = response.json()["access_token"]

    config = client.get(
        "/admin/api/v1/businesses/acme-cafe/config", headers=_auth_headers(token)
    )
    assert config.status_code == 200
    assert config.json()["display_name"] == "Acme Cafe"


def test_signup_default_llm_provider_is_google(client):
    response = client.post(
        "/admin/api/v1/auth/signup",
        json={
            "business_id": "acme-cafe",
            "display_name": "Acme Cafe",
            "owner_email": "owner@acme.test",
            "owner_password": "temp-pw",
        },
    )
    token = response.json()["access_token"]

    config = client.get(
        "/admin/api/v1/businesses/acme-cafe/config", headers=_auth_headers(token)
    )
    assert config.json()["llm"]["provider"] == "google"


def test_signup_rejects_duplicate_business_id(client):
    body = {
        "business_id": "acme-cafe",
        "display_name": "Acme Cafe",
        "owner_email": "owner@acme.test",
        "owner_password": "temp-pw",
    }
    client.post("/admin/api/v1/auth/signup", json=body)
    duplicate = client.post(
        "/admin/api/v1/auth/signup", json={**body, "owner_email": "other@acme.test"}
    )
    assert duplicate.status_code == 409


def test_signup_rejects_duplicate_owner_email(client):
    client.post(
        "/admin/api/v1/auth/signup",
        json={
            "business_id": "acme-cafe",
            "display_name": "Acme Cafe",
            "owner_email": "owner@acme.test",
            "owner_password": "temp-pw",
        },
    )
    duplicate = client.post(
        "/admin/api/v1/auth/signup",
        json={
            "business_id": "second-cafe",
            "display_name": "Second Cafe",
            "owner_email": "owner@acme.test",
            "owner_password": "temp-pw",
        },
    )
    assert duplicate.status_code == 409


def test_audit_log_records_writes(client):
    token = _login(client, "owner@kc.test")
    headers = _auth_headers(token)
    client.patch(
        "/admin/api/v1/businesses/kampuscrave/config",
        json={"business_logic": {"persona": "Updated persona."}},
        headers=headers,
    )

    response = client.get("/admin/api/v1/businesses/kampuscrave/audit-log", headers=headers)
    assert response.status_code == 200
    actions = [entry["action"] for entry in response.json()]
    assert "config.update" in actions
