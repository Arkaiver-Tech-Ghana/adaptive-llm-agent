from pathlib import Path

import pytest

from adaptive_agent.interfaces.whatsapp.registry import (
    WhatsAppRegistryError,
    build_business_registry,
)

FIXTURES = Path(__file__).parent / "fixtures" / "whatsapp_registry"


@pytest.fixture(autouse=True)
def _isolated_session_db(tmp_path, monkeypatch):
    # build_business_registry loads a real ConversationRuntime per Business,
    # which opens a SqliteSessionStore under SESSION_DB_DIR — keep that out
    # of the repo's own data/ directory.
    monkeypatch.setenv("SESSION_DB_DIR", str(tmp_path))


def test_builds_registry_indexed_by_phone_number_id():
    registry = build_business_registry(FIXTURES / "valid")

    assert set(registry) == {"phone-a", "phone-b"}
    assert registry["phone-a"].agent_core.business_config.business_id == "biz-a"
    assert registry["phone-b"].agent_core.business_config.business_id == "biz-b"


def test_missing_phone_number_id_on_enabled_entry_raises():
    with pytest.raises(WhatsAppRegistryError):
        build_business_registry(FIXTURES / "missing_phone_id")


def test_duplicate_phone_number_id_across_businesses_raises():
    with pytest.raises(WhatsAppRegistryError):
        build_business_registry(FIXTURES / "duplicate_phone_id")
