FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Dependencies first so they cache across source-only changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY . .
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Render (and most PaaS hosts) inject $PORT at runtime; default to 8000 for
# local `docker run`. Render's free plan has no persistent disk, so
# data/*.sqlite3 (including admin.sqlite3) is wiped on every deploy —
# reseed the KampusCrave menu and each Business's admin owner account on
# every boot; both seed steps are idempotent upserts, safe even when the
# disk *did* survive a restart.
CMD ["sh", "-c", "uv run python scripts/seed_kampuscrave_menu.py && uv run python scripts/seed_admin_owner.py && uv run uvicorn adaptive_agent.interfaces.whatsapp.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
