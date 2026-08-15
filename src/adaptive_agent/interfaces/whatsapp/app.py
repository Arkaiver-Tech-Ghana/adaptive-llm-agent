"""``create_app()`` factory + module-level ``app`` for uvicorn
(``uvicorn adaptive_agent.interfaces.whatsapp.app:app``). Reads WhatsApp
secrets and the optional non-secret overrides from the environment —
``load_dotenv()`` at import time matches ``cli.py``'s existing pattern.

``WHATSAPP_ACCESS_TOKEN``/``WHATSAPP_VERIFY_TOKEN``/``WHATSAPP_APP_SECRET``
are process-wide, not per-Business: both test numbers are expected to live
under one Meta App/WABA, not two separate Apps — the platform (Arkaiver),
not each Business, is the party with the Meta relationship. See
docs/adr/0005 if that assumption ever changes.
"""

import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

from adaptive_agent.interface_layer.dedupe import InMemoryDedupeStore
from adaptive_agent.interface_layer.rate_limiter import RateLimiter
from adaptive_agent.interface_layer.service import InterfaceLayer
from adaptive_agent.interfaces.whatsapp.registry import build_business_registry
from adaptive_agent.interfaces.whatsapp.router import build_router

logger = logging.getLogger(__name__)


async def _populate_business_registry(registry: dict, businesses_dir: Path) -> None:
    """Runs off the event loop thread so the (slow, per-Business NeMo Rail
    build) work can't block request handling while it's in flight. Mutates
    `registry` in place — `InterfaceLayer` already holds a reference to this
    same dict, so there's nothing else to wire up once loading finishes.
    Until then, every inbound webhook for a Business sees it as
    unregistered ("unknown_business", silently dropped) rather than the
    request hanging.
    """
    try:
        loaded = await asyncio.to_thread(build_business_registry, businesses_dir)
    except Exception:
        logger.exception("Failed to build WhatsApp business registry")
        return
    registry.update(loaded)


def create_app() -> FastAPI:
    businesses_dir = Path(os.environ.get("BUSINESSES_DIR", "businesses"))

    # Populated after startup by _populate_business_registry (see below) —
    # deliberately NOT built here. Uvicorn doesn't open its listening socket
    # until FastAPI's startup phase returns, so any slow work done directly
    # in create_app() (e.g. building a NemoRailChecker per Business) delays
    # the port coming up at all, which is what made Render's health check
    # time out rather than just respond slowly.
    business_registry: dict = {}

    rate_limiter = RateLimiter(
        max_per_minute=int(os.environ.get("RATE_LIMIT_PER_MINUTE", "20"))
    )
    dedupe_store = InMemoryDedupeStore(
        ttl_seconds=float(os.environ.get("DEDUPE_TTL_SECONDS", "86400"))
    )
    interface_layer = InterfaceLayer(
        business_registry=business_registry,
        rate_limiter=rate_limiter,
        dedupe_store=dedupe_store,
    )

    fastapi_app = FastAPI(title="Adaptive Agent — WhatsApp Webhook")

    @fastapi_app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    fastapi_app.include_router(
        build_router(
            interface_layer=interface_layer,
            verify_token=os.environ["WHATSAPP_VERIFY_TOKEN"],
            app_secret=os.environ["WHATSAPP_APP_SECRET"],
            access_token=os.environ["WHATSAPP_ACCESS_TOKEN"],
        )
    )

    @fastapi_app.on_event("startup")
    async def _start_registry_load() -> None:
        # Scheduled, not awaited: awaiting here would still block the
        # startup phase (and therefore the socket bind) until the whole
        # registry is built. `fastapi_app.state` keeps a strong reference
        # so the task isn't garbage-collected mid-flight.
        fastapi_app.state.registry_load_task = asyncio.create_task(
            _populate_business_registry(business_registry, businesses_dir)
        )

    return fastapi_app


load_dotenv()
app = create_app()
