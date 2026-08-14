"""Shared vocabulary between the LLM axis and the Tool Rail.

``ToolSpec`` is what an Agent Core hands an ``LLMProvider`` to describe an
available Tool; ``ToolCall`` is what the LLM hands back when it wants to
invoke one. Both are provider-agnostic — concrete providers translate them
to/from their own SDK's native tool-calling shape.
"""

from typing import Any

from pydantic import BaseModel


class ToolSpec(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]
    # Opaque, provider-specific round-trip data a concrete LLMProvider may
    # need to echo back verbatim when this ToolCall is replayed into a later
    # turn (e.g. Gemini's thought_signature — see google_provider.py). Every
    # other provider (and the Tool Rail, which only reads id/name/arguments)
    # ignores this field entirely; it exists so a provider's own replay
    # requirements never have to leak into the shared, provider-agnostic
    # ToolCall shape beyond "here's a bag you can stash it in."
    provider_data: dict[str, Any] | None = None
