# Business Config Schema

The Business Config is the single YAML file that turns the generic Agent
Core into one specific Business. Every axis from the PRD's "Modular config
layer" requirement is declared here — **wired** axes are read by the Agent
Core and/or the `ConversationRuntime` that wraps it in Rails (see
`conversation.py`); **stub** axes are validated but not yet acted on (they
ship Day 3 per the PRD timeline, and their `base.py` Protocol already
exists under `src/adaptive_agent/<axis>/`).

See `src/adaptive_agent/business_config/schema.py` for the authoritative
Pydantic definitions this table is generated from by hand — if the two
disagree, the schema file wins.

## Top level

| Field | Type | Required | Status | Notes |
|---|---|---|---|---|
| `business_id` | string | yes | wired | Slug identifying the Business, e.g. `kampuscrave`. |
| `display_name` | string | yes | wired | Human-readable name. |
| `enabled` | bool | no (default `true`) | wired | The "turn agent on/off" axis. `load_agent_core` raises `BusinessDisabledError` when false. |
| `llm` | [`LLMConfig`](#llmconfig) | yes | wired | Which LLM answers for this Business. |
| `context` | [`ContextConfig`](#contextconfig) | yes | wired | Where this Business's grounding documents live. |
| `business_logic` | [`BusinessLogicConfig`](#businesslogicconfig) | yes | wired | Persona, scope, tone. |
| `tools` | list of [`ToolConfig`](#toolconfig) | no (default `[]`) | wired | Read by `AgentCore.tool_specs` (offered to the LLM) and the Tool Rail (`requires_confirmation`), both invoked from `ConversationRuntime.handle_message`. |
| `storage` | [`StorageConfig`](#storageconfig) | no | `backend`/`database_id`/`schema_identity` stub, `table`/`columns` wired | See `docs/adr/0003` for the stub fields' design. |
| `auth` | [`AuthConfig`](#authconfig) | no | stub | Ships with the Interface Layer on Day 3. |
| `frontend_adapters` | list of [`FrontendAdapterConfig`](#frontendadapterconfig) | no (default: one `cli` entry) | `cli` informational, `whatsapp` wired | `whatsapp` entries are read by `interfaces/whatsapp/registry.py` at startup to route inbound webhook traffic; `cli` stays informational (the CLI harness ignores this list). |
| `rails` | [`RailsConfig`](#railsconfig) | no (defaults below) | wired | Per-Business Input/Output Rail toggles, read by `ConversationRuntime.handle_message` to decide whether to call the `RailChecker` at all for this Business. See `docs/adr/0004`. |

## `LLMConfig`

| Field | Type | Default | Notes |
|---|---|---|---|
| `provider` | string | `"anthropic"` | Looked up in `llm/registry.py`'s provider map. Currently `"anthropic"` or `"google"`. Unknown provider → `UnknownLLMProviderError`. |
| `model` | string | `"claude-sonnet-5"` | Passed straight to the provider, e.g. `"claude-sonnet-5"` for `anthropic` or `"gemini-flash-latest"` for `google`. |
| `max_tokens` | int | `1024` | Passed to the LLM call as-is. |
| `effort` | `"low"` \| `"medium"` \| `"high"` \| `"xhigh"` \| `"max"` \| `null` | `"medium"` | Anthropic-only: forwarded to `output_config.effort`. Ignored by the `google` provider. |

Two live providers exist to prove the LLM axis is swappable per Business
Config with zero core-code changes — see `CLAUDE.md`'s invariant. Each
reads its API key from the environment: `ANTHROPIC_API_KEY` for
`anthropic`, `GOOGLE_API_KEY` (or `GEMINI_API_KEY`) for `google`. Both
shipped Business Configs (`kampuscrave` and `hotel`) use `google` by
default — the project owner has no `ANTHROPIC_API_KEY`, so `google` is
what actually runs end to end in this environment. `anthropic` stays fully
wired and supported; flipping either Business Config's `llm.provider` back
to `anthropic` needs no code change, just an `ANTHROPIC_API_KEY`.

## `ContextConfig`

| Field | Type | Default | Notes |
|---|---|---|---|
| `source_type` | `"file"` | `"file"` | Only `"file"` is implemented Day 1; the field exists so `"database"`/`"api"` sources can be added later without a schema break. |
| `directory` | string | — (required) | Path to the context directory, **relative to the Business Config file's own location** — see `load_agent_core`. |
| `include_patterns` | list of string (glob) | `["*.md", "*.txt"]` | Matched non-recursively against `directory`. |

## `BusinessLogicConfig`

| Field | Type | Default | Notes |
|---|---|---|---|
| `persona` | string | — (required) | First section of the system prompt. |
| `scope_instructions` | string | — (required) | What the agent should/shouldn't answer. |
| `tone` | string \| null | `null` | Optional tone line in the system prompt. |
| `out_of_scope_response` | string \| null | `null` | If set, the model is told to use this exact phrasing outside scope. Enforcing it is a Day 2 Output Rail job — Day 1 only asks nicely. |

## `ToolConfig` (wired)

| Field | Type | Default | Notes |
|---|---|---|---|
| `name` | string | — (required) | Matches a name the loaded `ToolProvider.call()` implements; an LLM-requested call to a name not in this Business's `tools` list is DENYed by the Tool Rail (a hallucination guard) rather than executed. |
| `description` | string | — (required) | Handed to the LLM (via `ToolSpec`) so it knows the Tool exists and when to use it. Also used verbatim (lowercased) to build the Tool Rail's deterministic Confirmation prompt when `requires_confirmation` is true — see `conversation.py`'s `_build_confirmation_prompt`. |
| `input_schema` | dict (JSON Schema) | `{}` | Handed to the LLM (via `ToolSpec`) describing the Tool's call arguments. |
| `mcp_endpoint` | string \| null | `null` | Per the PRD, tools are MCP-compatible **in interface shape only** — `ToolProvider.call(name, arguments)` mirrors an MCP tool call, and `input_schema` is JSON-Schema like MCP's own tool descriptors. No real MCP wire-protocol server/client is stood up this sprint; this field is declared but unused — swapping in an MCP-backed `ToolProvider` later wouldn't require a schema change, but nothing today speaks the MCP protocol over this endpoint. |
| `requires_confirmation` | bool | `false` | Read by the Tool Rail (`rails/tool_rail.py`'s `decide()`) to choose `ALLOW` vs `REQUIRE_CONFIRMATION`. A Tool Rail `REQUIRE_CONFIRMATION` verdict stores a Confirmation Request in the Session until the Customer replies yes/no. |

## `StorageConfig` (`backend`/`database_id`/`schema_identity` stub, `table`/`columns` wired)

| Field | Type | Default | Notes |
|---|---|---|---|
| `backend` | `"none"` \| `"postgres"` \| `"sqlite"` | `"none"` | Not read by code — every Business's `ConversationRuntime` always gets a `SqliteSessionStore` + `SqliteCustomerStore` (plus, for `kampuscrave`, a `SqliteMenuRepository`) regardless of this value. `"sqlite"` here is truth-in-config only, documenting that this Business's session/customer/tool data genuinely lives in SQLite today — not a runtime switch. Both shipped Businesses (`hotel`, `kampuscrave`) are `"sqlite"` as of the live-menu-tool change; `"none"` is left as the schema default for a not-yet-onboarded Business. |
| `database_id` | string \| null | `null` | Part of the `database-id + schema-identity` key from `docs/adr/0003`. |
| `schema_identity` | string \| null | `null` | See above. |
| `table` | string \| null | `null` | Read by `tools/registry.py`'s kampuscrave factory and passed to `SqliteMenuRepository(table=...)`. `null` falls back to `SqliteMenuRepository.DEFAULT_TABLE` (`"menu_items"`). Lets a Business point the menu tool at whatever table its own database already uses — a table rename is a Business Config edit, not a source change. Must be a valid SQL identifier (`^[A-Za-z_][A-Za-z0-9_]*$`); a `BusinessConfigError` at load time otherwise, since this string is interpolated straight into SQL (sqlite3 can't bind identifiers with `?`). |
| `columns` | dict[string, string] \| null | `null` | Same idea, per-column: maps the logical fields `SqliteMenuRepository` needs (`name`, `category`, `price`, `stock_quantity`) to this Business's actual column names. `null` falls back to `SqliteMenuRepository.DEFAULT_COLUMNS` (identity mapping). If given, must supply exactly those four keys, each a valid SQL identifier — `SqliteMenuRepository` raises `InvalidMenuTableConfigError` otherwise (re-validated there, not just at config load, since the repository can be constructed directly). This type is a generic string->string map on purpose: `StorageConfig` doesn't know which fields any given repository needs, only the repository does. |

## `AuthConfig` (stub)

| Field | Type | Default | Notes |
|---|---|---|---|
| `type` | `"none"` \| `"api_key"` \| `"oauth"` | `"none"` | |

## `FrontendAdapterConfig` (`cli` informational, `whatsapp` wired)

| Field | Type | Default | Notes |
|---|---|---|---|
| `type` | `"cli"` \| `"web"` \| `"whatsapp"` | — (required) | |
| `enabled` | bool | `true` | |
| `phone_number_id` | string \| null | `null` | whatsapp-only routing key. The only thing WhatsApp Cloud API's inbound webhook payload gives to route a message to the right Business (`entry[].changes[].value.metadata.phone_number_id`). `registry.py` raises `WhatsAppRegistryError` at startup if an enabled `whatsapp` entry is missing this — fail fast rather than silently drop a Business from routing. Routing data, not a secret — belongs in committed `business.yaml`. |

## `RailsConfig` (wired)

| Field | Type | Default | Notes |
|---|---|---|---|
| `input_enabled` | bool | `true` | Whether the Input Rail runs for this Business. |
| `output_enabled` | bool | `true` | Whether the Output Rail runs for this Business. |
| `scope_description` | string \| null | `null` | Unused hook for a possible later spike into per-Business dynamic prompt injection into NeMo's self-check flows. Per-Business scope is enforced today via `business_logic.out_of_scope_response`/the system prompt, not here. |

This toggles Rails *per Business* — it does not select between per-Business
NeMo configs. The NeMo config itself (`nemo_rails/`) is one shared,
business-agnostic config for generic prompt-injection/jailbreak catching,
loaded the same way regardless of which Business is active; see
`docs/adr/0004` for why Rail behavior still lives inline in the Business
Config rather than a separate file, and `nemo_rails/config.yml`'s own
comments for how NeMo's self-check LLM is wired to Google Gemini via
`langchain-google-genai` (pinned to a version older than the one where a
NeMo/LangChain `max_tokens` compatibility gap was introduced).

## Onboarding a new Business

Add a new YAML file under `businesses/<slug>/business.yaml` with its own
`context/` directory, and point an interface (currently only the CLI) at
it via `--business`. No code under `src/adaptive_agent/` changes — that's
`CLAUDE.md`'s invariant, proven structurally by this file existing at all.
