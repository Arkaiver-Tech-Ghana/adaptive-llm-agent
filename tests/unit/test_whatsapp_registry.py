from pathlib import Path
from types import SimpleNamespace

import pytest

from adaptive_agent.business_config.loader import load_business_config
from adaptive_agent.interfaces.whatsapp.registry import (
    WhatsAppRegistryError,
    build_business_registry,
)

FIXTURES = Path(__file__).parent / "fixtures" / "whatsapp_registry"


def _fake_runtime_loader(business_yaml: Path) -> SimpleNamespace:
    """Stands in for the real load_conversation_runtime, which constructs a
    real NemoRailChecker (needs an LLM API key) — these tests are only
    about the routing/fail-fast logic in registry.py, not runtime loading."""
    config = load_business_config(business_yaml)
    return SimpleNamespace(agent_core=SimpleNamespace(business_config=config))


def test_builds_registry_indexed_by_phone_number_id():
    registry = build_business_registry(FIXTURES / "valid", runtime_loader=_fake_runtime_loader)

    assert set(registry) == {"phone-a", "phone-b"}
    assert registry["phone-a"].agent_core.business_config.business_id == "biz-a"
    assert registry["phone-b"].agent_core.business_config.business_id == "biz-b"


def test_missing_phone_number_id_on_enabled_entry_raises():
    with pytest.raises(WhatsAppRegistryError):
        build_business_registry(FIXTURES / "missing_phone_id", runtime_loader=_fake_runtime_loader)


def test_duplicate_phone_number_id_across_businesses_raises():
    with pytest.raises(WhatsAppRegistryError):
        build_business_registry(
            FIXTURES / "duplicate_phone_id", runtime_loader=_fake_runtime_loader
        )
