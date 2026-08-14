"""Business Config schema.

Declares every axis from the PRD's "Modular config layer" requirement so a
reviewer can see the full design from this file alone. Day 1 only wires up
``llm``, ``context``, ``business_logic``, and ``enabled`` into the Agent
Core — the rest (``tools``, ``storage``, ``auth``, ``frontend_adapters``)
are declared-but-unwired stubs for Day 2/3.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    provider: str = "anthropic"
    model: str = "claude-sonnet-5"
    max_tokens: int = 1024
    effort: Literal["low", "medium", "high", "xhigh", "max"] | None = "medium"


class ContextConfig(BaseModel):
    source_type: Literal["file"] = "file"
    directory: str
    include_patterns: list[str] = Field(default_factory=lambda: ["*.md", "*.txt"])


class BusinessLogicConfig(BaseModel):
    persona: str
    scope_instructions: str
    tone: str | None = None
    out_of_scope_response: str | None = None


class ToolConfig(BaseModel):
    """A Tool a Business exposes to its Agent Core. ``description`` and
    ``input_schema`` are what get handed to the LLM (via ``ToolSpec``) so it
    knows the Tool exists and how to call it; ``requires_confirmation`` is
    read by the Tool Rail to decide whether a call needs a Confirmation
    before it executes."""

    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    mcp_endpoint: str | None = None
    requires_confirmation: bool = False


class StorageConfig(BaseModel):
    """Stub. See docs/adr/0003 for the database-id + schema-identity design."""

    backend: Literal["none", "postgres", "sqlite"] = "none"
    database_id: str | None = None
    schema_identity: str | None = None


class AuthConfig(BaseModel):
    """Stub."""

    type: Literal["none", "api_key", "oauth"] = "none"


class FrontendAdapterConfig(BaseModel):
    """Informational only Day 1 — no adapter is implemented yet."""

    type: Literal["cli", "web", "whatsapp"]
    enabled: bool = True


class RailsConfig(BaseModel):
    """Per-Business Rail on/off switches. See docs/adr/0004 for why this
    lives inline in the Business Config rather than a separate file.

    The NeMo config itself (``nemo_rails/``) is one shared, business-agnostic
    config for generic injection/jailbreak catching — these flags don't
    select between per-Business NeMo configs, they just let a Business turn
    a Rail off outright. ``scope_description`` is an unused hook for a later
    spike into per-Business dynamic prompt injection into NeMo's self-check
    flows; per-Business scope boundaries are enforced today at the Agent
    Core's ``business_logic.out_of_scope_response``/system-prompt layer.
    """

    input_enabled: bool = True
    output_enabled: bool = True
    scope_description: str | None = None


class BusinessConfig(BaseModel):
    business_id: str
    display_name: str
    enabled: bool = True
    llm: LLMConfig
    context: ContextConfig
    business_logic: BusinessLogicConfig
    tools: list[ToolConfig] = Field(default_factory=list)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    frontend_adapters: list[FrontendAdapterConfig] = Field(
        default_factory=lambda: [FrontendAdapterConfig(type="cli")]
    )
    rails: RailsConfig = Field(default_factory=RailsConfig)
