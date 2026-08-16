from pathlib import Path

import pytest
import yaml

from adaptive_agent.business_config.loader import load_business_config
from adaptive_agent.business_config.writer import (
    ConfigPatchError,
    update_business_config,
)

_MINIMAL_CONFIG = {
    "business_id": "kampuscrave",
    "display_name": "KampusCrave",
    "llm": {"provider": "google", "model": "gemini-flash-lite-latest"},
    "context": {"directory": "context"},
    "business_logic": {
        "persona": "Original persona.",
        "scope_instructions": "Original scope.",
        "tone": "warm",
    },
    "tools": [
        {"name": "check_menu_item", "description": "Check an item.", "requires_confirmation": False}
    ],
    "storage": {"backend": "sqlite"},
}


def _write_config(tmp_path: Path) -> Path:
    path = tmp_path / "business.yaml"
    path.write_text(yaml.safe_dump(_MINIMAL_CONFIG))
    return path


def test_update_persona_persists_and_leaves_other_fields_untouched(tmp_path):
    path = _write_config(tmp_path)
    updated = update_business_config(path, {"business_logic": {"persona": "New persona."}})

    assert updated.business_logic.persona == "New persona."
    assert updated.business_logic.tone == "warm"

    reloaded = load_business_config(path)
    assert reloaded.business_logic.persona == "New persona."
    assert reloaded.display_name == "KampusCrave"


def test_update_display_name(tmp_path):
    path = _write_config(tmp_path)
    updated = update_business_config(path, {"display_name": "Renamed Cafe"})

    assert updated.display_name == "Renamed Cafe"
    assert load_business_config(path).display_name == "Renamed Cafe"


def test_update_tools_replaces_the_whole_list(tmp_path):
    path = _write_config(tmp_path)
    new_tools = [{"name": "book_room", "description": "Book a room.", "requires_confirmation": True}]
    updated = update_business_config(path, {"tools": new_tools})

    assert [t.name for t in updated.tools] == ["book_room"]
    assert updated.tools[0].requires_confirmation is True


def test_update_llm_provider_and_model(tmp_path):
    path = _write_config(tmp_path)
    updated = update_business_config(path, {"llm": {"provider": "anthropic", "model": "claude-sonnet-5"}})

    assert updated.llm.provider == "anthropic"
    assert updated.llm.model == "claude-sonnet-5"


def test_rejects_patch_touching_admin_immutable_field(tmp_path):
    path = _write_config(tmp_path)
    with pytest.raises(ConfigPatchError):
        update_business_config(path, {"storage": {"backend": "postgres"}})


def test_rejects_patch_touching_unknown_top_level_field(tmp_path):
    path = _write_config(tmp_path)
    with pytest.raises(ConfigPatchError):
        update_business_config(path, {"enabled": False})


def test_rejects_patch_that_produces_an_invalid_config(tmp_path):
    path = _write_config(tmp_path)
    with pytest.raises(ConfigPatchError):
        update_business_config(path, {"business_logic": {"persona": None}})
