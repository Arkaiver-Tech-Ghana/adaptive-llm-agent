"""A second concrete LLM provider — Google's Gemini API — proving the LLM
axis is swappable per Business Config, per CLAUDE.md's invariant."""

from google import genai
from google.genai import types

from adaptive_agent.llm.base import LLMResponse

_ROLE_MAP = {"user": "user", "assistant": "model"}


class GoogleLLMProvider:
    """Implements LLMProvider. Reads GOOGLE_API_KEY (or GEMINI_API_KEY) from
    the environment.

    Unlike anthropic.Anthropic(), genai.Client() validates the API key
    eagerly at construction time, so the client is built lazily on first
    ``generate()`` call — constructing this provider must not require the
    key to be present (registry/wiring tests build providers without one).
    """

    def __init__(self, model: str):
        self._model = model
        self._client: genai.Client | None = None

    def generate(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int,
    ) -> LLMResponse:
        if self._client is None:
            self._client = genai.Client()

        contents = [
            types.Content(role=_ROLE_MAP[m["role"]], parts=[types.Part(text=m["content"])])
            for m in messages
        ]
        response = self._client.models.generate_content(
            model=self._model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
            ),
        )
        return LLMResponse(text=response.text, raw=response)
