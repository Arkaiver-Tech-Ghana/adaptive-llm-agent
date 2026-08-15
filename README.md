# Adaptive Business Chat Agent

One agent core, wrapped by NeMo Guardrails, serving multiple unrelated
businesses off one config-driven codebase — see `prd-adaptive-agent.md` for
the full spec, `CLAUDE.md` for the standing architecture invariant, and
`CONTEXT.md` for the domain glossary.

## Setup

```bash
uv sync --dev
cp .env.example .env
# edit .env: set GOOGLE_API_KEY — both shipped Business Configs default to
# `google`, and NeMo's rails self-check LLM (nemo_rails/config.yml) also
# runs on Google Gemini, so this one key is all the default demo path
# needs. ANTHROPIC_API_KEY is only needed if you flip a Business Config's
# llm.provider to `anthropic`.
```

`.env` is loaded automatically by both the CLI and the test suite (via
`python-dotenv`) and is gitignored — never commit it.

## Run the CLI

```bash
uv run adaptive-agent-cli --business businesses/kampuscrave/business.yaml
```

## Run the WhatsApp webhook

The Interface Layer (rate limiting, dedupe, request-size bounds) and the
WhatsApp Frontend Adapter serve every enabled Business from one process,
routed by the receiving number's `phone_number_id`.

```bash
# .env also needs: WHATSAPP_ACCESS_TOKEN, WHATSAPP_VERIFY_TOKEN,
# WHATSAPP_APP_SECRET, and each business.yaml needs its real
# phone_number_id filled in (see docs/business-config-schema.md).
uv run uvicorn adaptive_agent.interfaces.whatsapp.app:app --port 8000
```

Point WhatsApp Cloud API's webhook at `https://<your-public-url>/webhook/whatsapp`
(e.g. via `ngrok http 8000` for local testing) and subscribe to the
`messages` field. See `docs/adr/0005` for why the webhook's signature check
lives in the adapter rather than behind `AuthProvider`.

## Tests

```bash
uv run pytest                     # unit tests only (integration is skipped without GOOGLE_API_KEY)
uv run pytest -m integration      # integration test only, requires GOOGLE_API_KEY
```

See `docs/business-config-schema.md` for the Business Config field reference.
