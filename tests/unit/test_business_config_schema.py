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
    assert config.llm.provider == "google"
    assert config.llm.model == "gemini-flash-lite-latest"
    assert config.llm.effort == "medium"


def test_rails_defaults_to_both_enabled():
    config = BusinessConfig.model_validate(VALID_MINIMAL)
    assert config.rails.input_enabled is True
    assert config.rails.output_enabled is True
    assert config.rails.scope_description is None


def test_rails_config_overridable():
    data = {
        **VALID_MINIMAL,
        "rails": {
            "input_enabled": False,
            "output_enabled": True,
            "scope_description": "Only KampusCrave menu/hours/location questions.",
        },
    }
    config = BusinessConfig.model_validate(data)
    assert config.rails.input_enabled is False
    assert config.rails.output_enabled is True
    assert config.rails.scope_description == "Only KampusCrave menu/hours/location questions."


def test_tool_config_requires_name_and_description():
    with pytest.raises(ValidationError):
        BusinessConfig.model_validate(
            {**VALID_MINIMAL, "tools": [{"name": "check_room_availability"}]}
        )


def test_tool_config_parses_description_and_input_schema():
    data = {
        **VALID_MINIMAL,
        "tools": [
            {
                "name": "check_room_availability",
                "description": "Check whether a room type is available for given dates.",
                "input_schema": {
                    "type": "object",
                    "properties": {"room_type": {"type": "string"}},
                    "required": ["room_type"],
                },
                "requires_confirmation": False,
            }
        ],
    }
    config = BusinessConfig.model_validate(data)
    tool = config.tools[0]
    assert tool.name == "check_room_availability"
    assert tool.description == "Check whether a room type is available for given dates."
    assert tool.input_schema == {
        "type": "object",
        "properties": {"room_type": {"type": "string"}},
        "required": ["room_type"],
    }
    assert tool.requires_confirmation is False
    assert tool.mcp_endpoint is None


def test_tool_config_input_schema_defaults_to_empty_dict():
    data = {
        **VALID_MINIMAL,
        "tools": [{"name": "book_room", "description": "Book a room."}],
    }
    config = BusinessConfig.model_validate(data)
    assert config.tools[0].input_schema == {}


def test_storage_table_and_columns_default_to_none():
    config = BusinessConfig.model_validate(VALID_MINIMAL)
    assert config.storage.table is None
    assert config.storage.columns is None


def test_storage_table_and_columns_parse_when_given():
    data = {
        **VALID_MINIMAL,
        "storage": {
            "backend": "sqlite",
            "table": "products",
            "columns": {
                "name": "item_name",
                "category": "cat",
                "price": "unit_price",
                "stock_quantity": "qty",
            },
        },
    }
    config = BusinessConfig.model_validate(data)
    assert config.storage.table == "products"
    assert config.storage.columns == {
        "name": "item_name",
        "category": "cat",
        "price": "unit_price",
        "stock_quantity": "qty",
    }


def test_storage_table_rejects_non_identifier():
    data = {
        **VALID_MINIMAL,
        "storage": {"table": "menu_items; DROP TABLE menu_items;--"},
    }
    with pytest.raises(ValidationError):
        BusinessConfig.model_validate(data)


def test_storage_columns_rejects_non_identifier_value():
    data = {**VALID_MINIMAL, "storage": {"columns": {"name": "name; --"}}}
    with pytest.raises(ValidationError):
        BusinessConfig.model_validate(data)
