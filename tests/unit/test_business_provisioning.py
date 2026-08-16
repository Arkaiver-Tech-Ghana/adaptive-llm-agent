from pathlib import Path

import pytest

from adaptive_agent.admin.auth import verify_password
from adaptive_agent.admin.base import AdminRole
from adaptive_agent.admin.sqlite_store import SqliteAdminStore
from adaptive_agent.business_config.loader import load_business_config
from adaptive_agent.business_config.provisioning import (
    BusinessAlreadyExistsError,
    InvalidBusinessIdError,
    OwnerEmailAlreadyExistsError,
    create_business_config,
    provision_business,
)


def _store(tmp_path: Path) -> SqliteAdminStore:
    return SqliteAdminStore(tmp_path / "admin.sqlite3")


def test_create_business_config_defaults_to_google_llm_provider():
    config = create_business_config("acme-cafe", "Acme Cafe")
    assert config.llm.provider == "google"
    assert config.llm.model == "gemini-flash-lite-latest"


def test_create_business_config_rejects_invalid_business_id():
    with pytest.raises(InvalidBusinessIdError):
        create_business_config("Not A Valid Id!", "Acme Cafe")


def test_provision_business_writes_config_and_context_dir_and_owner(tmp_path):
    businesses_dir = tmp_path / "businesses"
    store = _store(tmp_path)

    owner = provision_business(
        business_id="acme-cafe",
        display_name="Acme Cafe",
        owner_email="owner@acme.test",
        owner_password="temp-pw",
        businesses_dir=businesses_dir,
        admin_store=store,
    )

    assert owner.role == AdminRole.OWNER
    assert owner.business_id == "acme-cafe"
    assert verify_password("temp-pw", owner.password_hash)

    config = load_business_config(businesses_dir / "acme-cafe" / "business.yaml")
    assert config.business_id == "acme-cafe"
    assert config.display_name == "Acme Cafe"
    assert (businesses_dir / "acme-cafe" / "context").is_dir()

    stored = store.get_user_by_email("owner@acme.test")
    assert stored == owner


def test_provision_business_rejects_duplicate_business_id(tmp_path):
    businesses_dir = tmp_path / "businesses"
    store = _store(tmp_path)
    provision_business("acme-cafe", "Acme Cafe", "a@acme.test", "pw", businesses_dir, store)

    with pytest.raises(BusinessAlreadyExistsError):
        provision_business("acme-cafe", "Acme Cafe Again", "b@acme.test", "pw", businesses_dir, store)


def test_provision_business_rejects_duplicate_owner_email(tmp_path):
    businesses_dir = tmp_path / "businesses"
    store = _store(tmp_path)
    provision_business("acme-cafe", "Acme Cafe", "owner@acme.test", "pw", businesses_dir, store)

    with pytest.raises(OwnerEmailAlreadyExistsError):
        provision_business(
            "acme-cafe-2", "Acme Cafe 2", "owner@acme.test", "pw", businesses_dir, store
        )


def test_provision_business_leaves_no_directory_behind_on_duplicate_email(tmp_path):
    businesses_dir = tmp_path / "businesses"
    store = _store(tmp_path)
    provision_business("acme-cafe", "Acme Cafe", "owner@acme.test", "pw", businesses_dir, store)

    with pytest.raises(OwnerEmailAlreadyExistsError):
        provision_business(
            "second-cafe", "Second Cafe", "owner@acme.test", "pw", businesses_dir, store
        )

    assert not (businesses_dir / "second-cafe").exists()
