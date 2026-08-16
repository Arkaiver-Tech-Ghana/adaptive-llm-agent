"""Scans every Business's ``business.yaml`` at startup and indexes a ready
``ConversationRuntime`` by ``phone_number_id`` — the only thing WhatsApp
Cloud API's inbound webhook gives to route an inbound message to the right
Business. One running FastAPI process serves every enabled Business at
once; no restart to "swap" between them.

A problem isolated to one Business's config (malformed YAML, a missing or
duplicate phone_number_id, a runtime that fails to build) is logged and
that Business alone is left out of the registry — it must never take
every other Business off WhatsApp routing too, since this loop runs across
every Business in one process.
"""

import logging
from collections.abc import Callable
from pathlib import Path

from adaptive_agent.business_config.loader import (
    BusinessConfigError,
    load_business_config,
)
from adaptive_agent.conversation import ConversationRuntime, load_conversation_runtime

logger = logging.getLogger(__name__)


def build_business_registry(
    businesses_dir: Path,
    runtime_loader: Callable[[Path], ConversationRuntime] = load_conversation_runtime,
) -> dict[str, ConversationRuntime]:
    """``runtime_loader`` defaults to the real ``load_conversation_runtime``
    (which constructs a real NemoRailChecker, requiring an LLM API key) —
    overridable so the routing/isolation logic here is unit-testable
    without one."""
    registry: dict[str, ConversationRuntime] = {}

    for business_yaml in sorted(businesses_dir.glob("*/business.yaml")):
        try:
            config = load_business_config(business_yaml)
        except BusinessConfigError:
            logger.exception("Skipping %s: invalid Business Config", business_yaml)
            continue

        if not config.enabled:
            continue

        for adapter in config.frontend_adapters:
            if adapter.type != "whatsapp" or not adapter.enabled:
                continue

            if not adapter.phone_number_id:
                logger.error(
                    "Skipping Business '%s' (%s): enabled whatsapp frontend "
                    "adapter has no phone_number_id",
                    config.business_id,
                    business_yaml,
                )
                continue

            if adapter.phone_number_id in registry:
                logger.error(
                    "Skipping Business '%s' (%s): phone_number_id '%s' is "
                    "already claimed by another Business",
                    config.business_id,
                    business_yaml,
                    adapter.phone_number_id,
                )
                continue

            try:
                registry[adapter.phone_number_id] = runtime_loader(business_yaml)
            except Exception:
                logger.exception(
                    "Skipping Business '%s' (%s): failed to build its runtime",
                    config.business_id,
                    business_yaml,
                )

    return registry
