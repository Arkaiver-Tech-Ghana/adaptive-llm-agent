"""The Agent Core: LLM + a loaded Business Config, handling informative
(RAG-style) requests. Identical code for every Business — behavior differs
only by which Business Config is loaded.

``load_agent_core`` is the single entry point every interface (CLI, and
later web/WhatsApp) calls. It never imports a concrete provider by name —
only the Protocol types and each axis's registry/factory — so onboarding a
Business never requires touching this file. Tools, storage, auth, and
session never appear here: wiring them in only when they're real (Day 2+)
keeps this file honest about what's actually implemented.
"""

from pathlib import Path

from adaptive_agent.business_config.loader import load_business_config
from adaptive_agent.business_config.schema import BusinessConfig
from adaptive_agent.context.base import ContextProvider
from adaptive_agent.context.file_provider import FileContextProvider
from adaptive_agent.llm.base import LLMProvider
from adaptive_agent.llm.registry import build_llm_provider
from adaptive_agent.prompt import build_system_prompt


class BusinessDisabledError(Exception):
    pass


class AgentCore:
    def __init__(
        self,
        business_config: BusinessConfig,
        llm_provider: LLMProvider,
        context_provider: ContextProvider,
    ):
        self.business_config = business_config
        self.llm_provider = llm_provider
        self.context_provider = context_provider

    def respond(self, user_message: str, history: list[dict[str, str]] | None = None) -> str:
        context_docs = self.context_provider.load()
        system = build_system_prompt(self.business_config, context_docs)
        messages = [*(history or []), {"role": "user", "content": user_message}]
        result = self.llm_provider.generate(
            system=system,
            messages=messages,
            max_tokens=self.business_config.llm.max_tokens,
        )
        return result.text


def load_agent_core(business_config_path: Path) -> AgentCore:
    config = load_business_config(business_config_path)
    if not config.enabled:
        raise BusinessDisabledError(f"Business '{config.business_id}' is disabled")

    llm_provider = build_llm_provider(config.llm)
    context_provider = FileContextProvider(
        directory=business_config_path.parent / config.context.directory,
        include_patterns=config.context.include_patterns,
    )
    return AgentCore(config, llm_provider, context_provider)
