import pytest

from adaptive_agent.business_config.schema import LLMConfig
from adaptive_agent.llm.anthropic_provider import AnthropicLLMProvider
from adaptive_agent.llm.registry import UnknownLLMProviderError, build_llm_provider


def test_build_anthropic_provider_no_network_call():
    provider = build_llm_provider(LLMConfig(provider="anthropic", model="claude-sonnet-5"))
    assert isinstance(provider, AnthropicLLMProvider)
    assert provider._model == "claude-sonnet-5"


def test_unknown_provider_raises_helpful_error():
    with pytest.raises(UnknownLLMProviderError, match="unknown-llm"):
        build_llm_provider(LLMConfig(provider="unknown-llm"))
