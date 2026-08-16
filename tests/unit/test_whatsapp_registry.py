from pathlib import Path
from types import SimpleNamespace

from adaptive_agent.business_config.loader import (
    BusinessConfigError,
    load_business_config,
)
from adaptive_agent.interfaces.whatsapp.registry import build_business_registry

FIXTURES = Path(__file__).parent / "fixtures" / "whatsapp_registry"


def _fake_runtime_loader(business_yaml: Path) -> SimpleNamespace:
    """Stands in for the real load_conversation_runtime, which constructs a
    real NemoRailChecker (needs an LLM API key) — these tests are only
    about the routing/isolation logic in registry.py, not runtime loading."""
    config = load_business_config(business_yaml)
    return SimpleNamespace(agent_core=SimpleNamespace(business_config=config))


def test_builds_registry_indexed_by_phone_number_id():
    registry = build_business_registry(FIXTURES / "valid", runtime_loader=_fake_runtime_loader)

    assert set(registry) == {"phone-a", "phone-b"}
    assert registry["phone-a"].agent_core.business_config.business_id == "biz-a"
    assert registry["phone-b"].agent_core.business_config.business_id == "biz-b"


def test_missing_phone_number_id_skips_only_that_business():
    registry = build_business_registry(
        FIXTURES / "missing_phone_id", runtime_loader=_fake_runtime_loader
    )

    assert set(registry) == {"phone-b"}
    assert registry["phone-b"].agent_core.business_config.business_id == "biz-b"


def test_duplicate_phone_number_id_keeps_first_and_skips_the_rest():
    registry = build_business_registry(
        FIXTURES / "duplicate_phone_id", runtime_loader=_fake_runtime_loader
    )

    # sorted() glob order makes biz-a the first claimant of "shared-phone".
    assert set(registry) == {"shared-phone"}
    assert registry["shared-phone"].agent_core.business_config.business_id == "biz-a"


def test_malformed_config_skips_only_that_business():
    registry = build_business_registry(
        FIXTURES / "malformed_config", runtime_loader=_fake_runtime_loader
    )

    assert set(registry) == {"phone-b"}
    assert registry["phone-b"].agent_core.business_config.business_id == "biz-b"


def test_runtime_loader_failure_skips_only_that_business():
    def _flaky_runtime_loader(business_yaml: Path) -> SimpleNamespace:
        config = load_business_config(business_yaml)
        if config.business_id == "biz-a":
            raise BusinessConfigError("simulated runtime build failure")
        return SimpleNamespace(agent_core=SimpleNamespace(business_config=config))

    registry = build_business_registry(FIXTURES / "valid", runtime_loader=_flaky_runtime_loader)

    assert set(registry) == {"phone-b"}
    assert registry["phone-b"].agent_core.business_config.business_id == "biz-b"
