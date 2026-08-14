"""Maps an LLMConfig.provider string to a concrete LLMProvider instance."""

from collections.abc import Callable

from adaptive_agent.business_config.schema import LLMConfig
from adaptive_agent.llm.anthropic_provider import AnthropicLLMProvider
from adaptive_agent.llm.base import LLMProvider


class UnknownLLMProviderError(Exception):
    pass


_PROVIDERS: dict[str, Callable[[LLMConfig], LLMProvider]] = {
    "anthropic": lambda cfg: AnthropicLLMProvider(model=cfg.model, effort=cfg.effort),
}


def build_llm_provider(config: LLMConfig) -> LLMProvider:
    try:
        factory = _PROVIDERS[config.provider]
    except KeyError:
        known = ", ".join(sorted(_PROVIDERS))
        raise UnknownLLMProviderError(
            f"Unknown LLM provider '{config.provider}'. Known providers: {known}"
        ) from None
    return factory(config)
