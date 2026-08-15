"""Scans every Business's ``business.yaml`` at startup and indexes a ready
``ConversationRuntime`` by ``phone_number_id`` — the only thing WhatsApp
Cloud API's inbound webhook gives to route an inbound message to the right
Business. One running FastAPI process serves every enabled Business at
once; no restart to "swap" between them.
"""

from collections.abc import Callable
from pathlib import Path

from adaptive_agent.business_config.loader import load_business_config
from adaptive_agent.conversation import ConversationRuntime, load_conversation_runtime


class WhatsAppRegistryError(Exception):
    pass


def build_business_registry(
    businesses_dir: Path,
    runtime_loader: Callable[[Path], ConversationRuntime] = load_conversation_runtime,
) -> dict[str, ConversationRuntime]:
    """``runtime_loader`` defaults to the real ``load_conversation_runtime``
    (which constructs a real NemoRailChecker, requiring an LLM API key) —
    overridable so the routing/fail-fast logic here is unit-testable
    without one."""
    registry: dict[str, ConversationRuntime] = {}

    for business_yaml in sorted(businesses_dir.glob("*/business.yaml")):
        config = load_business_config(business_yaml)
        if not config.enabled:
            continue

        for adapter in config.frontend_adapters:
            if adapter.type != "whatsapp" or not adapter.enabled:
                continue

            if not adapter.phone_number_id:
                raise WhatsAppRegistryError(
                    f"Business '{config.business_id}' ({business_yaml}) has an "
                    "enabled whatsapp frontend adapter but no phone_number_id set"
                )

            if adapter.phone_number_id in registry:
                raise WhatsAppRegistryError(
                    f"phone_number_id '{adapter.phone_number_id}' is claimed by "
                    f"more than one Business (duplicate found in {business_yaml})"
                )

            registry[adapter.phone_number_id] = runtime_loader(business_yaml)

    return registry
