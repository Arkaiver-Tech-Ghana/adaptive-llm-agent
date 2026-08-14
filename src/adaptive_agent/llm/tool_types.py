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
