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
# local `docker run`.
CMD ["sh", "-c", "uv run uvicorn adaptive_agent.interfaces.whatsapp.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
