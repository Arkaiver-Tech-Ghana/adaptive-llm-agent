from pathlib import Path

import pytest

from adaptive_agent.business_config.loader import (
    BusinessConfigError,
    load_business_config,
)

FIXTURES = Path(__file__).parent / "fixtures" / "business_configs"


def test_load_valid_config():
    config = load_business_config(FIXTURES / "valid_minimal.yaml")
    assert config.business_id == "testbiz"


def test_load_missing_file_raises():
    with pytest.raises(BusinessConfigError, match="not found"):
        load_business_config(FIXTURES / "does_not_exist.yaml")


def test_load_malformed_yaml_raises():
    with pytest.raises(BusinessConfigError, match="Malformed YAML"):
        load_business_config(FIXTURES / "malformed.yaml")


def test_load_failing_validation_raises():
    with pytest.raises(BusinessConfigError, match="Invalid Business Config"):
        load_business_config(FIXTURES / "missing_required_field.yaml")
