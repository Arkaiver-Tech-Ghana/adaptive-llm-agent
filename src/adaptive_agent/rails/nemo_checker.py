"""``RailChecker`` backed by NeMo Guardrails.

Bookends the Agent Core rather than owning its main LLM call: NeMo only
ever runs in "checkpoint" mode here (``options={"rails": ["input"]}`` /
``["output"]``), each call scoped to exactly one Rail. See
``nemo_rails/config.yml`` for the shared, business-agnostic config and why
its self-check LLM is Google Gemini (via LangChain's ``google_genai``
engine, on a pinned ``langchain-google-genai`` version — see that file's
comment for the compatibility gap this works around).
"""

from pathlib import Path
from typing import Any

from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.llm.frameworks import set_default_framework
from nemoguardrails.rails.llm.options import GenerationOptions

from adaptive_agent.rails.base import RailVerdict

# NeMo's self-check model here is Google Gemini via the `google_genai`
# LangChain provider (see nemo_rails/config.yml's comment for why), which
# isn't one of NeMo's built-in default-framework providers (openai/azure/
# nim/ollama) either. NeMo's LangChain integration covers it, but only once
# switched on — the default framework only knows OpenAI-compatible
# endpoints. This is a process-global switch (NeMo has no per-``LLMRails``
# -instance framework selector), which is fine here: NeMo is only ever used
# for rails checks in this project, always via LangChain.
set_default_framework("langchain")

# Placeholder prior turn fed to NeMo when checking output only: NeMo's
# `self_check_output` action reads the bot response from the *last*
# message, but only populates that context when there's a preceding `user`
# turn in the conversation at all (confirmed empirically — a bare single
# `assistant` message never activates the output rail). The Business's
# actual system prompt/scope prompt already used to produce the response
# under check plays that role for our own prompt template (`../../nemo_rails
# /config.yml`'s `self_check_output` task doesn't reference `user_input`),
# so the placeholder's content is inert — it only needs to exist.
_OUTPUT_CHECK_PLACEHOLDER_USER_TURN = "(prior customer message, not re-checked here)"


class NemoRailChecker:
    """Implements ``RailChecker`` via a NeMo ``LLMRails`` instance loaded
    from a NeMo config directory (``nemo_rails/`` by default)."""

    def __init__(self, config_dir: str | Path):
        self._rails = LLMRails(RailsConfig.from_path(str(config_dir)))

    def check_input(self, message: str) -> RailVerdict:
        result = self._rails.generate(
            messages=[{"role": "user", "content": message}],
            options=GenerationOptions(rails=["input"], log={"activated_rails": True}),
        )
        return self._to_verdict(result)

    def check_output(self, response_text: str) -> RailVerdict:
        result = self._rails.generate(
            messages=[
                {"role": "user", "content": _OUTPUT_CHECK_PLACEHOLDER_USER_TURN},
                {"role": "assistant", "content": response_text},
            ],
            options=GenerationOptions(rails=["output"], log={"activated_rails": True}),
        )
        return self._to_verdict(result)

    @staticmethod
    def _to_verdict(result: Any) -> RailVerdict:
        text = _extract_text(result.response)
        allowed = True
        activated_rail: str | None = None
        activated_rails = result.log.activated_rails if result.log else []
        for rail in activated_rails:
            # "stop" is Colang's abort signal — every refusal flow in
            # nemo_rails/rails/*.co ends with it. A rail can activate
            # (run its check) without stopping the pipeline; only a stop
            # means this Rail actually blocked the message.
            if "stop" in rail.decisions:
                allowed = False
                activated_rail = rail.name
                break
        return RailVerdict(allowed=allowed, text=text, activated_rail=activated_rail)


def _extract_text(response: Any) -> str:
    if isinstance(response, list) and response:
        last = response[-1]
        if isinstance(last, dict):
            return str(last.get("content", ""))
        return str(last)
    return str(response)
