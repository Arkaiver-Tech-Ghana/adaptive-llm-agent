# Adaptive Business Chat Agent

One agent core, wrapped by NeMo Guardrails, serving multiple unrelated
businesses off one config-driven codebase — see `prd-adaptive-agent.md` for
the full spec, `CLAUDE.md` for the standing architecture invariant, and
`CONTEXT.md` for the domain glossary.

## Setup

```bash
uv sync --dev
export ANTHROPIC_API_KEY=your-key-here  # only needed to actually talk to the LLM
```

## Run the CLI

```bash
uv run adaptive-agent-cli --business businesses/kampuscrave/business.yaml
```

## Tests

```bash
uv run pytest                     # unit tests only (integration is skipped without ANTHROPIC_API_KEY)
uv run pytest -m integration      # integration test only, requires ANTHROPIC_API_KEY
```

See `docs/business-config-schema.md` for the Business Config field reference.
