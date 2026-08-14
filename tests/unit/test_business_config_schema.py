import pytest
from pydantic import ValidationError

from adaptive_agent.business_config.schema import BusinessConfig

VALID_MINIMAL = {
    "business_id": "testbiz",
    "display_name": "Test Business",
    "llm": {"provider": "anthropic", "model": "claude-sonnet-5"},
    "context": {"directory": "context"},
    "business_logic": {
        "persona": "You are a test assistant.",
        "scope_instructions": "Answer only from the given context.",
    },
}


def test_valid_minimal_config_parses():
    config = BusinessConfig.model_validate(VALID_MINIMAL)
    assert config.business_id == "testbiz"
    assert config.llm.model == "claude-sonnet-5"
    assert config.context.directory == "context"
    assert config.business_logic.persona == "You are a test assistant."


def test_missing_business_logic_raises():
    data = {k: v for k, v in VALID_MINIMAL.items() if k != "business_logic"}
    with pytest.raises(ValidationError):
        BusinessConfig.model_validate(data)


def test_missing_context_directory_raises():
    data = {**VALID_MINIMAL, "context": {}}
    with pytest.raises(ValidationError):
        BusinessConfig.model_validate(data)


def test_stub_axes_default_correctly():
    config = BusinessConfig.model_validate(VALID_MINIMAL)
    assert config.tools == []
    assert config.storage.backend == "none"
    assert config.auth.type == "none"
    assert config.enabled is True
    assert [a.type for a in config.frontend_adapters] == ["cli"]


def test_llm_defaults():
    data = {**VALID_MINIMAL, "llm": {}}
    config = BusinessConfig.model_validate(data)
    assert config.llm.provider == "anthropic"
    assert config.llm.model == "claude-sonnet-5"
    assert config.llm.effort == "medium"
