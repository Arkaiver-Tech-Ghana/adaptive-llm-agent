from pathlib import Path

from adaptive_agent.agent_core import AgentCore
from adaptive_agent.business_config.schema import BusinessConfig
from adaptive_agent.context.file_provider import FileContextProvider
from tests.unit.fakes import FakeLLMProvider

FIXTURES = Path(__file__).parent / "fixtures" / "context_files"

CONFIG = BusinessConfig.model_validate(
    {
        "business_id": "testbiz",
        "display_name": "Test Business",
        "llm": {"max_tokens": 512},
        "context": {"directory": "context_files", "include_patterns": ["*.md"]},
        "business_logic": {
            "persona": "You are the Test Business assistant.",
            "scope_instructions": "Answer only from context.",
        },
    }
)


def _build_core(fake: FakeLLMProvider) -> AgentCore:
    context_provider = FileContextProvider(FIXTURES, include_patterns=["*.md"])
    return AgentCore(CONFIG, fake, context_provider)


def test_respond_returns_fake_text():
    fake = FakeLLMProvider(canned_text="the answer")
    core = _build_core(fake)
    assert core.respond("What's on the menu?") == "the answer"


def test_respond_passes_persona_and_context_in_system_prompt():
    fake = FakeLLMProvider()
    core = _build_core(fake)
    core.respond("hi")
    assert fake.last_system is not None
    assert "You are the Test Business assistant." in fake.last_system
    assert "sample context content" in fake.last_system


def test_respond_uses_configured_max_tokens():
    fake = FakeLLMProvider()
    core = _build_core(fake)
    core.respond("hi")
    assert fake.last_max_tokens == 512


def test_respond_includes_history_and_user_message():
    fake = FakeLLMProvider()
    core = _build_core(fake)
    history = [{"role": "user", "content": "earlier"}, {"role": "assistant", "content": "reply"}]
    core.respond("follow up", history=history)
    assert fake.last_messages == [*history, {"role": "user", "content": "follow up"}]
