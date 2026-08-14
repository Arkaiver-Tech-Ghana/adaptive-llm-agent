"""Loads a Business Config from a YAML file."""

from pathlib import Path

import yaml
from pydantic import ValidationError

from adaptive_agent.business_config.schema import BusinessConfig


class BusinessConfigError(Exception):
    """Raised when a Business Config file can't be loaded or fails validation."""


def load_business_config(path: Path) -> BusinessConfig:
    if not path.is_file():
        raise BusinessConfigError(f"Business Config file not found: {path}")

    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise BusinessConfigError(f"Malformed YAML in {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise BusinessConfigError(f"Business Config at {path} must be a YAML mapping")

    try:
        return BusinessConfig.model_validate(raw)
    except ValidationError as exc:
        raise BusinessConfigError(f"Invalid Business Config at {path}:\n{exc}") from exc
