"""The one concrete LLM provider Day 1 ships: Anthropic's Claude API."""

import anthropic

from adaptive_agent.llm.base import LLMResponse


class AnthropicLLMProvider:
    """Implements LLMProvider. Reads ANTHROPIC_API_KEY from the environment."""

    def __init__(self, model: str, effort: str | None = None):
        self._client = anthropic.Anthropic()
        self._model = model
        self._effort = effort

    def generate(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int,
    ) -> LLMResponse:
        kwargs: dict = {}
        if self._effort:
            kwargs["output_config"] = {"effort": self._effort}

        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            **kwargs,
        )
        text = next(block.text for block in response.content if block.type == "text")
        return LLMResponse(text=text, raw=response)
