"""The Conversation Runtime: where the four Rails actually wrap the Agent
Core (CLAUDE.md's "Rails" section — "nothing reaches or leaves unchecked").

Lives outside ``agent_core.py`` on purpose: Rails wrap the Agent Core, they
aren't part of it. ``ConversationRuntime.handle_message`` is the single
entry point every Frontend Adapter (today: the CLI) calls per inbound
message; it owns the full per-turn flow — Customer visit bookkeeping,
Input Rail, pending-Confirmation resolution, Data Rail, the Agent Core
turn itself, Tool Rail, Output Rail, and Session history — so no interface
layer has to re-implement any of it.
"""

import os
from pathlib import Path
from typing import Literal

from adaptive_agent.agent_core import AgentCore, load_agent_core
from adaptive_agent.business_config.schema import ToolConfig
from adaptive_agent.customers.base import CustomerStore
from adaptive_agent.customers.sqlite_store import SqliteCustomerStore
from adaptive_agent.entities.sqlite_repository import SqliteEntityRepository
from adaptive_agent.llm.base import LLMResponse
from adaptive_agent.llm.tool_types import ToolCall
from adaptive_agent.rails.base import RailChecker
from adaptive_agent.rails.data_rail import check_data_access, check_tool_data_access
from adaptive_agent.rails.nemo_checker import NemoRailChecker
from adaptive_agent.rails.tool_rail import ToolRailDecision
from adaptive_agent.rails.tool_rail import decide as decide_tool_rail
from adaptive_agent.session.base import ConfirmationRequest, SessionStore
from adaptive_agent.session.sqlite_store import SqliteSessionStore
from adaptive_agent.tools.base import ToolProvider
from adaptive_agent.tools.composite_provider import CompositeToolProvider
from adaptive_agent.tools.entity_crud_provider import EntityCrudToolProvider
from adaptive_agent.tools.mcp_provider import MCPToolProvider
from adaptive_agent.tools.registry import build_tool_provider

_YES_REPLIES = {"yes", "y", "yeah", "yep", "confirm", "ok", "okay"}
_NO_REPLIES = {"no", "n", "nope", "cancel"}

_CANCELLATION_TEXT = "No problem — cancelled, nothing was done."
_NUDGE_TEXT = "Sorry, I didn't catch that — please reply yes or no."
_DENY_TEXT = "Sorry, I can't do that."


def parse_confirmation_reply(text: str) -> Literal["yes", "no"] | None:
    """Classifies a Customer's reply to a pending Confirmation Request as
    yes/no/neither. Day 2 only ever sees plain-text synonyms (see
    CONTEXT.md's Confirmation entry); Day 3's WhatsApp quick-reply button
    payload (a fixed button id/value rather than free text) plugs in here
    later — the Tool Rail checks the reply against the expected shape, it
    doesn't care which form produced it.
    """
    normalized = text.strip().lower()
    if normalized in _YES_REPLIES:
        return "yes"
    if normalized in _NO_REPLIES:
        return "no"
    return None


class ConversationRuntime:
    """Wraps one loaded Agent Core with the four Rails and a Session Store.
    One instance per Business (see ``load_conversation_runtime``)."""

    def __init__(
        self,
        agent_core: AgentCore,
        tool_provider: ToolProvider,
        session_store: SessionStore,
        rail_checker: RailChecker,
        customer_store: CustomerStore,
    ):
        self.agent_core = agent_core
        self.tool_provider = tool_provider
        self.session_store = session_store
        self.rail_checker = rail_checker
        self.customer_store = customer_store

    def handle_message(self, session_key: str, user_message: str) -> str:
        business_config = self.agent_core.business_config

        # 0. Record the visit before anything else, including the Input
        # Rail — pure bookkeeping (first/last_seen only), no content is
        # exposed either way, so a blocked/adversarial message still
        # counts as a visit. This is the one thing in handle_message that
        # deliberately runs ahead of the Input Rail; everything else
        # respects rule 1 below.
        customer_id = session_key.split(":", 1)[1]
        self.customer_store.record_visit(customer_id)

        # 1. Input Rail always runs first among content-bearing steps,
        # even on a bare "yes"/"no" reply while a Confirmation is pending
        # — "nothing reaches or leaves unchecked" is not optional. A
        # blocked message never reaches the Agent Core (or the
        # pending-confirmation resolution below) and its refusal text
        # skips the Output Rail: that text IS what the Input Rail already
        # decided the Customer should see, so re-checking it as output
        # would be circular, not "leaving unchecked".
        if business_config.rails.input_enabled:
            input_verdict = self.rail_checker.check_input(user_message)
            if not input_verdict.allowed:
                self.session_store.append(session_key, "user", user_message)
                self.session_store.append(session_key, "assistant", input_verdict.text)
                return input_verdict.text

        pending = self.session_store.get_pending_confirmation(session_key)
        if pending is not None:
            final_text = self._resolve_confirmation(session_key, pending, user_message)
        else:
            final_text = self._fresh_turn(session_key, user_message)

        final_text = self._check_output(final_text)

        self.session_store.append(session_key, "user", user_message)
        self.session_store.append(session_key, "assistant", final_text)
        return final_text

    def _resolve_confirmation(
        self, session_key: str, pending: ConfirmationRequest, user_message: str
    ) -> str:
        reply = parse_confirmation_reply(user_message)

        if reply == "yes":
            # continue_with_tool_result appends a synthetic assistant-tool-call
            # turn onto this history, immediately followed by the tool-result
            # turn. Some providers (Gemini) reject a function-call turn that
            # doesn't immediately follow a real user turn or a function-result
            # turn — and get_history() alone never ends in "user" here: the
            # Confirmation Request's deterministic prompt (or a nudge, for a
            # prior ambiguous reply) was already persisted as the trailing
            # assistant turn. Splice in this "yes" so the reconstructed
            # transcript is valid for every provider, not just the lenient ones.
            history = [
                *self.session_store.get_history(session_key),
                {"role": "user", "content": user_message},
            ]
            tool_result = self.tool_provider.call(
                pending.tool_call.name, pending.tool_call.arguments
            )
            result = self.agent_core.continue_with_tool_result(
                history, pending.tool_call, tool_result
            )
            self.session_store.set_pending_confirmation(session_key, None)
            return result.text

        if reply == "no":
            self.session_store.set_pending_confirmation(session_key, None)
            return _CANCELLATION_TEXT

        # Neither yes nor no: leave the pending Confirmation Request intact
        # and do NOT fall through to a fresh Agent Core turn.
        return _NUDGE_TEXT

    def _fresh_turn(self, session_key: str, user_message: str) -> str:
        business_config = self.agent_core.business_config
        history = self.session_store.get_history(session_key)

        # Data Rail checkpoint: a no-op passthrough today (see
        # rails/data_rail.py), but called explicitly so "Data Rail" maps to
        # real code, not just a diagram box.
        context_docs = self.agent_core.context_provider.load()
        check_data_access(context_docs, business_config.business_id)

        if business_config.tools:
            result = self.agent_core.respond_with_tools(
                user_message, history, tools=self.agent_core.tool_specs
            )
        else:
            # respond() intentionally has no tool_calls concept (kampuscrave's
            # path, unchanged from Day 1) — wrap its plain str in a minimal
            # LLMResponse so the rest of this method can treat both branches
            # uniformly.
            result = LLMResponse(text=self.agent_core.respond(user_message, history))

        # Only the first tool call is considered — parallel/multiple tool
        # calls in one turn are explicitly out of scope for Day 2.
        if result.tool_calls:
            # respond_with_tools appended user_message onto its own copy of
            # `history` internally (agent_core.py) without mutating this
            # list, so it's spliced in again here — `_handle_tool_call`'s
            # ALLOW branch feeds this straight into continue_with_tool_result,
            # which needs history ending in this turn's real user message
            # immediately before the assistant-tool-call turn it synthesizes
            # (see the matching comment in `_resolve_confirmation`).
            history_with_this_turn = [*history, {"role": "user", "content": user_message}]
            return self._handle_tool_call(session_key, history_with_this_turn, result.tool_calls[0])

        return result.text

    def _handle_tool_call(
        self, session_key: str, history: list, tool_call: ToolCall
    ) -> str:
        business_config = self.agent_core.business_config
        tool_decision = decide_tool_rail(tool_call, business_config.tools)

        if tool_decision == ToolRailDecision.ALLOW:
            tool_result = self.tool_provider.call(tool_call.name, tool_call.arguments)
            # Data Rail checkpoint: a read-only Tool call is retrieval too
            # (issue #16) — same passthrough-today checkpoint as the
            # context-doc path in _fresh_turn, applied to the Tool's
            # result before it reaches the Agent Core.
            tool_result = check_tool_data_access(tool_result, business_config.business_id)
            result = self.agent_core.continue_with_tool_result(history, tool_call, tool_result)
            return result.text

        if tool_decision == ToolRailDecision.REQUIRE_CONFIRMATION:
            self.session_store.set_pending_confirmation(
                session_key, ConfirmationRequest(tool_call=tool_call)
            )
            return _build_confirmation_prompt(tool_call, business_config.tools)

        # DENY: the tool name isn't in this Business's catalog — a
        # hallucination guard. No execution.
        return _DENY_TEXT

    def _check_output(self, text: str) -> str:
        business_config = self.agent_core.business_config
        if not business_config.rails.output_enabled:
            return text
        output_verdict = self.rail_checker.check_output(text)
        if not output_verdict.allowed:
            return output_verdict.text
        return text


def _build_confirmation_prompt(tool_call: ToolCall, tool_configs: list[ToolConfig]) -> str:
    """Deterministic templated Confirmation prompt — not another LLM call.
    A safety-critical "are you sure?" should state exactly what's about to
    happen in a predictable format, not a paraphrase that could drift."""
    description = next(
        (tc.description for tc in tool_configs if tc.name == tool_call.name),
        tool_call.name,
    )
    return (
        f"You're about to {description.lower()} with: {tool_call.arguments}. "
        "Reply yes to confirm or no to cancel."
    )


def load_conversation_runtime(business_config_path: Path) -> ConversationRuntime:
    """Loads a Business Config and wires a ready ConversationRuntime: an
    Agent Core (via load_agent_core), and a per-Business ToolProvider (via
    the tools registry) composed with the generic entity-CRUD provider every
    Business gets for its own Custom Tables (tools/entity_crud_provider.py)
    and an MCP provider for whichever of the Business's Tools declare
    ``mcp_endpoint`` (tools/mcp_provider.py) — see CompositeToolProvider.
    Also a SqliteSessionStore and SqliteCustomerStore sharing one file per
    Business under SESSION_DB_DIR (``data/`` by default), and a
    NemoRailChecker pointed at the repo-root nemo_rails/ config dir."""
    agent_core = load_agent_core(business_config_path)
    nemo_config_dir = Path(__file__).resolve().parents[2] / "nemo_rails"
    rail_checker = NemoRailChecker(nemo_config_dir)
    session_db_dir = Path(os.environ.get("SESSION_DB_DIR", "data"))
    db_path = session_db_dir / f"{agent_core.business_config.business_id}.sqlite3"
    base_provider = build_tool_provider(
        agent_core.business_config.tool_provider, agent_core.business_config.storage, db_path
    )
    mcp_endpoints = {
        t.name: t.mcp_endpoint for t in agent_core.business_config.tools if t.mcp_endpoint
    }
    # Local providers first, MCP last: dispatch falls through on
    # UnknownToolError, so there is no reason to pay for a network round
    # trip on a name one of the in-process providers already handles.
    tool_provider = CompositeToolProvider(
        [
            base_provider,
            EntityCrudToolProvider(SqliteEntityRepository(db_path)),
            MCPToolProvider(mcp_endpoints),
        ]
    )
    return ConversationRuntime(
        agent_core=agent_core,
        tool_provider=tool_provider,
        session_store=SqliteSessionStore(db_path),
        rail_checker=rail_checker,
        customer_store=SqliteCustomerStore(db_path),
    )
