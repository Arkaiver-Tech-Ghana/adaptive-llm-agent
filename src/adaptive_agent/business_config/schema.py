"""Business Config schema.

Declares every axis from the PRD's "Modular config layer" requirement so a
reviewer can see the full design from this file alone. Day 1 only wires up
``llm``, ``context``, ``business_logic``, and ``enabled`` into the Agent
Core — the rest (``tools``, ``storage``, ``auth``, ``frontend_adapters``)
are declared-but-unwired stubs for Day 2/3.
"""

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# SQL identifiers only — table/column names below get interpolated directly
# into query strings (sqlite3 can't bind identifiers with `?`), so this is
# the injection guard. Applies even though the source is a trusted config
# file, not user input: defense in depth, and it turns a typo'd column name
# into a fail-fast config error instead of a broken query at call time.
_SQL_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


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
    """``backend``/``database_id``/``schema_identity`` are a stub — see
    docs/adr/0003 for the database-id + schema-identity design.

    ``table``/``columns`` are wired: they let a Business point a SQL-backed
    repository (e.g. SqliteMenuRepository) at whatever table/column names
    its own database actually uses, so renaming a table or column is a
    Business Config edit, not a source change. Generic string->string here
    on purpose — this type doesn't know which logical fields any given
    repository needs; the repository validates ``columns`` has the keys it
    requires (see SqliteMenuRepository).
    """

    backend: Literal["none", "postgres", "sqlite"] = "none"
    database_id: str | None = None
    schema_identity: str | None = None
    table: str | None = None
    columns: dict[str, str] | None = None

    @field_validator("table")
    @classmethod
    def _table_is_valid_identifier(cls, value: str | None) -> str | None:
        if value is not None and not _SQL_IDENTIFIER_RE.match(value):
            raise ValueError(
                f"storage.table must be a valid SQL identifier, got {value!r}"
            )
        return value

    @field_validator("columns")
    @classmethod
    def _columns_are_valid_identifiers(
        cls, value: dict[str, str] | None
    ) -> dict[str, str] | None:
        if value is not None:
            for field_name, column_name in value.items():
                if not _SQL_IDENTIFIER_RE.match(column_name):
                    raise ValueError(
                        f"storage.columns[{field_name!r}] must be a valid SQL identifier, "
                        f"got {column_name!r}"
                    )
        return value


class AuthConfig(BaseModel):
    """Stub."""

    type: Literal["none", "api_key", "oauth"] = "none"


class FrontendAdapterConfig(BaseModel):
    """``cli`` stays informational (the CLI harness doesn't read this list —
    see ``interfaces/cli.py``). ``whatsapp`` is wired Day 3: ``registry.py``
    scans every Business's enabled ``whatsapp`` entry and indexes its
    ConversationRuntime by ``phone_number_id``, the only thing WhatsApp
    Cloud API's inbound webhook gives to route an inbound message to the
    right Business."""

    type: Literal["cli", "web", "whatsapp"]
    enabled: bool = True
    phone_number_id: str | None = None


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
