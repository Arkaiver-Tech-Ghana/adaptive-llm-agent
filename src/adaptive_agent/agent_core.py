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

import json
from pathlib import Path
from typing import Any

from adaptive_agent.business_config.loader import load_business_config
from adaptive_agent.business_config.schema import BusinessConfig
from adaptive_agent.context.base import ContextProvider
from adaptive_agent.context.file_provider import FileContextProvider
from adaptive_agent.llm.base import LLMProvider, LLMResponse
from adaptive_agent.llm.registry import build_llm_provider
from adaptive_agent.llm.tool_types import ToolCall, ToolSpec
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

    def respond_with_tools(
        self,
        user_message: str,
        history: list[dict[str, Any]] | None,
        tools: list[ToolSpec],
    ) -> LLMResponse:
        """Same context-loading/system-prompt-building as ``respond()``, but
        offers ``tools`` to the LLM and returns the full ``LLMResponse`` so
        the caller (the Tool Rail, via the conversation orchestrator) can
        inspect ``tool_calls`` rather than only getting back text."""
        context_docs = self.context_provider.load()
        system = build_system_prompt(self.business_config, context_docs)
        messages = [*(history or []), {"role": "user", "content": user_message}]
        return self.llm_provider.generate(
            system=system,
            messages=messages,
            max_tokens=self.business_config.llm.max_tokens,
            tools=tools,
        )

    def continue_with_tool_result(
        self,
        history: list[dict[str, Any]],
        tool_call: ToolCall,
        tool_result: Any,
    ) -> LLMResponse:
        """Feed an executed Tool's result back to the LLM for a final
        natural-language reply. Rebuilds the system prompt (context is still
        relevant) and appends the normalized assistant-tool-call and
        tool-result turns onto ``history``. Called with no ``tools`` — this
        follow-up turn is meant to produce a final reply, not request
        another Tool call (parallel/chained Tool calls are out of scope)."""
        context_docs = self.context_provider.load()
        system = build_system_prompt(self.business_config, context_docs)
        messages = [
            *history,
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [tool_call.model_dump()],
            },
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(tool_result),
            },
        ]
        return self.llm_provider.generate(
            system=system,
            messages=messages,
            max_tokens=self.business_config.llm.max_tokens,
        )

    @property
    def tool_specs(self) -> list[ToolSpec]:
        """The Business Config's Tools, translated to what the LLM axis
        needs to describe them (``ToolConfig`` also carries Tool Rail-only
        fields like ``requires_confirmation`` that the LLM has no business
        seeing)."""
        return [
            ToolSpec(
                name=t.name,
                description=t.description,
                input_schema=t.input_schema,
            )
            for t in self.business_config.tools
            if t.enabled
        ]


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
