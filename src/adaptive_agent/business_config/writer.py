"""Writes back the subset of a Business Config that issue #17 puts in scope
for owner-editable Admin CRUD: persona/tone/scope/out-of-scope text, the
tool list, and LLM provider/model. Everything else (storage, auth,
frontend_adapters, rails) is admin-immutable for now — a patch touching
those keys is rejected rather than silently applied.

``loader.py`` only reads; this is the write half, used by the Admin
Interface Layer, never by the chat-facing runtime.
"""

import os
from pathlib import Path

import yaml
from pydantic import ValidationError

from adaptive_agent.business_config.loader import load_business_config
from adaptive_agent.business_config.schema import BusinessConfig

# Dotted paths a config patch is allowed to touch. Anything else in the
# patch is an admin-immutable field — reject rather than silently apply.
_EDITABLE_FIELDS = frozenset(
    {
        "business_logic.persona",
        "business_logic.tone",
        "business_logic.scope_instructions",
        "business_logic.out_of_scope_response",
        "tools",
        "llm.provider",
        "llm.model",
    }
)


class ConfigPatchError(Exception):
    """Raised when a patch touches a field outside _EDITABLE_FIELDS, or the
    patched config fails BusinessConfig validation."""


def _patch_keys(patch: dict, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    for key, value in patch.items():
        dotted = f"{prefix}{key}"
        # "tools" is atomic (a list, not a nested mapping to walk into) —
        # any edit to it replaces the whole list, so it's always in scope
        # as a whole rather than diffed key-by-key.
        if isinstance(value, dict) and dotted != "tools":
            keys |= _patch_keys(value, prefix=f"{dotted}.")
        else:
            keys.add(dotted)
    return keys


def _deep_merge(base: dict, patch: dict) -> dict:
    merged = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def update_business_config(path: Path, patch: dict) -> BusinessConfig:
    disallowed = _patch_keys(patch) - _EDITABLE_FIELDS
    if disallowed:
        raise ConfigPatchError(f"Patch touches admin-immutable field(s): {sorted(disallowed)}")

    current = load_business_config(path)
    merged_raw = _deep_merge(current.model_dump(mode="json"), patch)

    try:
        updated = BusinessConfig.model_validate(merged_raw)
    except ValidationError as exc:
        raise ConfigPatchError(f"Patched config is invalid:\n{exc}") from exc

    # Atomic write: a request reading business.yaml mid-write (the runtime
    # reloads it per-process, not per-request, but a future hot-reload path
    # or a concurrent admin write shouldn't ever see a half-written file).
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(yaml.safe_dump(merged_raw, sort_keys=False))
    os.replace(tmp_path, path)

    return updated
