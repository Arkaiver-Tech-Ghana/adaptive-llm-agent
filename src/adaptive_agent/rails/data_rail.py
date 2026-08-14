"""The Data Rail — governs what data the Agent Core may retrieve
(CONTEXT.md; this project's name for NeMo's retrieval rail).
"""

from adaptive_agent.context.base import ContextDocument


def check_data_access(
    context_docs: list[ContextDocument], business_id: str
) -> list[ContextDocument]:
    """Defense-in-depth checkpoint: today an identity passthrough, since
    FileContextProvider is already constructed per-Business and there's
    no shared/multi-tenant data store yet (storage stays stubbed — see
    CLAUDE.md's non-goals). Exists as a named, tested checkpoint so
    "Data Rail" maps to real code for a reviewer, not just a diagram
    box. Becomes a real filter once storage/RLS (ADR 0001) lands with
    per-customer data.
    """
    return context_docs
