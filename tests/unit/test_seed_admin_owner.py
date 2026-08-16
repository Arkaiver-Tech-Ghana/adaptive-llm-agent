from pathlib import Path

from adaptive_agent.admin.auth import verify_password
from adaptive_agent.admin.sqlite_store import SqliteAdminStore


def test_seeds_owner_accounts_from_env_vars(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SESSION_DB_DIR", str(tmp_path))
    monkeypatch.setenv("ADMIN_OWNER_EMAIL_KAMPUSCRAVE", "owner@kc.test")
    monkeypatch.setenv("ADMIN_OWNER_PASSWORD_KAMPUSCRAVE", "seed-password")
    monkeypatch.delenv("ADMIN_OWNER_EMAIL_HOTEL", raising=False)
    monkeypatch.delenv("ADMIN_OWNER_PASSWORD_HOTEL", raising=False)

    from scripts.seed_admin_owner import main

    main()

    store = SqliteAdminStore(tmp_path / "admin.sqlite3")
    user = store.get_user_by_email("owner@kc.test")
    assert user is not None
    assert user.business_id == "kampuscrave"
    assert verify_password("seed-password", user.password_hash)
    assert store.get_user_by_email("owner@hotel.test") is None


def test_seed_is_safe_to_rerun(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SESSION_DB_DIR", str(tmp_path))
    monkeypatch.setenv("ADMIN_OWNER_EMAIL_KAMPUSCRAVE", "owner@kc.test")
    monkeypatch.setenv("ADMIN_OWNER_PASSWORD_KAMPUSCRAVE", "first-password")

    from scripts.seed_admin_owner import main

    main()
    monkeypatch.setenv("ADMIN_OWNER_PASSWORD_KAMPUSCRAVE", "second-password")
    main()

    store = SqliteAdminStore(tmp_path / "admin.sqlite3")
    user = store.get_user_by_email("owner@kc.test")
    assert verify_password("second-password", user.password_hash)
