# Business Config Schema

The Business Config is the single YAML file that turns the generic Agent
Core into one specific Business. Every axis from the PRD's "Modular config
layer" requirement is declared here — **wired** axes are read by the Day 1
Agent Core; **stub** axes are validated but not yet acted on (they ship
Day 2/3 per the PRD timeline, and their `base.py` Protocol already exists
under `src/adaptive_agent/<axis>/`).

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
| `tools` | list of [`ToolConfig`](#toolconfig) | no (default `[]`) | stub | Declared shape only — no tool-calling Day 1. |
| `storage` | [`StorageConfig`](#storageconfig) | no | stub | See `docs/adr/0003` for the design this anticipates. |
| `auth` | [`AuthConfig`](#authconfig) | no | stub | Ships with the Interface Layer on Day 3. |
| `frontend_adapters` | list of [`FrontendAdapterConfig`](#frontendadapterconfig) | no (default: one `cli` entry) | informational | No real adapter contract exists yet — this documents intent, not behavior. |

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
`anthropic`, `GOOGLE_API_KEY` (or `GEMINI_API_KEY`) for `google`. The
`kampuscrave` Business Config uses `google` by default.

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

## `ToolConfig` (stub)

| Field | Type | Default | Notes |
|---|---|---|---|
| `name` | string | — (required) | |
| `mcp_endpoint` | string \| null | `null` | Per the PRD, tools are MCP-compatible. |
| `requires_confirmation` | bool | `false` | Maps to the Tool Rail's confirmation gate (Day 2). |

## `StorageConfig` (stub)

| Field | Type | Default | Notes |
|---|---|---|---|
| `backend` | `"none"` \| `"postgres"` \| `"sqlite"` | `"none"` | |
| `database_id` | string \| null | `null` | Part of the `database-id + schema-identity` key from `docs/adr/0003`. |
| `schema_identity` | string \| null | `null` | See above. |

## `AuthConfig` (stub)

| Field | Type | Default | Notes |
|---|---|---|---|
| `type` | `"none"` \| `"api_key"` \| `"oauth"` | `"none"` | |

## `FrontendAdapterConfig` (informational)

| Field | Type | Default | Notes |
|---|---|---|---|
| `type` | `"cli"` \| `"web"` \| `"whatsapp"` | — (required) | |
| `enabled` | bool | `true` | |

## Onboarding a new Business

Add a new YAML file under `businesses/<slug>/business.yaml` with its own
`context/` directory, and point an interface (currently only the CLI) at
it via `--business`. No code under `src/adaptive_agent/` changes — that's
`CLAUDE.md`'s invariant, proven structurally by this file existing at all.
