"""The admin frontend is a cross-origin browser client (separate Vercel
deploy) hitting /admin/api/v1/* directly — without CORS headers every such
call is blocked by the browser before it reaches AdminInterfaceLayer.
Covers create_app()'s CORSMiddleware wiring, not the admin router's own
logic (already covered by test_admin_router.py)."""

from pathlib import Path

from fastapi.testclient import TestClient

from adaptive_agent.interfaces.whatsapp.app import create_app


def _app_env(monkeypatch, tmp_path: Path, **extra: str) -> None:
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "verify-me")
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "shh")
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "token")
    monkeypatch.setenv("ADMIN_JWT_SECRET", "test-secret")
    monkeypatch.setenv("BUSINESSES_DIR", str(tmp_path / "businesses"))
    monkeypatch.setenv("SESSION_DB_DIR", str(tmp_path / "data"))
    for key, value in extra.items():
        monkeypatch.setenv(key, value)


def test_admin_route_allows_configured_origin(monkeypatch, tmp_path):
    _app_env(monkeypatch, tmp_path, ADMIN_CORS_ORIGINS="https://admin.example.com")
    client = TestClient(create_app())

    response = client.options(
        "/admin/api/v1/auth/login",
        headers={
            "Origin": "https://admin.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.headers["access-control-allow-origin"] == "https://admin.example.com"


def test_admin_route_rejects_unconfigured_origin(monkeypatch, tmp_path):
    _app_env(monkeypatch, tmp_path, ADMIN_CORS_ORIGINS="https://admin.example.com")
    client = TestClient(create_app())

    response = client.options(
        "/admin/api/v1/auth/login",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in response.headers


def test_default_cors_origin_is_local_vite_dev_server(monkeypatch, tmp_path):
    _app_env(monkeypatch, tmp_path)
    client = TestClient(create_app())

    response = client.options(
        "/admin/api/v1/auth/login",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
