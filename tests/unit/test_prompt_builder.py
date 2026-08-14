from adaptive_agent.business_config.schema import BusinessConfig
from adaptive_agent.context.base import ContextDocument
from adaptive_agent.prompt import build_system_prompt

BASE_CONFIG = BusinessConfig.model_validate(
    {
        "business_id": "testbiz",
        "display_name": "Test Business",
        "llm": {},
        "context": {"directory": "context"},
        "business_logic": {
            "persona": "You are the Test Business assistant.",
            "scope_instructions": "Answer only menu and hours questions.",
            "out_of_scope_response": "I can only help with menu and hours.",
        },
    }
)


def test_prompt_contains_persona_and_scope():
    prompt = build_system_prompt(BASE_CONFIG, [])
    assert "You are the Test Business assistant." in prompt
    assert "Answer only menu and hours questions." in prompt
    assert "I can only help with menu and hours." in prompt


def test_prompt_contains_every_context_doc():
    docs = [
        ContextDocument(name="menu.md", content="Burgers: $5"),
        ContextDocument(name="hours.md", content="9am-9pm"),
    ]
    prompt = build_system_prompt(BASE_CONFIG, docs)
    assert "## menu.md" in prompt
    assert "Burgers: $5" in prompt
    assert "## hours.md" in prompt
    assert "9am-9pm" in prompt


def test_empty_context_list_does_not_crash():
    prompt = build_system_prompt(BASE_CONFIG, [])
    assert isinstance(prompt, str)
    assert len(prompt) > 0
