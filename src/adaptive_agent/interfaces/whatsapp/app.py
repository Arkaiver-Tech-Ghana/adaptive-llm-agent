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
from fastapi.middleware.cors import CORSMiddleware

from adaptive_agent.admin.interface_layer import AdminInterfaceLayer
from adaptive_agent.admin.sqlite_store import SqliteAdminStore
from adaptive_agent.interface_layer.dedupe import InMemoryDedupeStore
from adaptive_agent.interface_layer.rate_limiter import RateLimiter
from adaptive_agent.interface_layer.service import InterfaceLayer
from adaptive_agent.interfaces.admin.entities_router import build_entities_router
from adaptive_agent.interfaces.admin.router import build_admin_router
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

    # The admin frontend (adaptive-llm-agent-admin) is a separate, cross-
    # origin Vercel deploy calling /admin/api/v1/* straight from the
    # browser — without CORS every such call is blocked before it reaches
    # these routes. The WhatsApp webhook below is server-to-server (Meta ->
    # this API), never browser-invoked, so applying this app-wide doesn't
    # affect it: no Origin header, no CORS check. allow_credentials stays
    # False since auth is a bearer token in a header, not a cookie.
    admin_origins = [
        origin.strip()
        for origin in os.environ.get("ADMIN_CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ]
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=admin_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

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

    # Admin API (issue #17): one shared, platform-wide data/admin.sqlite3
    # (ADR 0006), not one file per Business like the WhatsApp registry
    # above. Cheap to build eagerly at startup, unlike business_registry —
    # no NeMo Rail build involved — so it doesn't need the deferred-task
    # dance _populate_business_registry uses.
    session_db_dir = Path(os.environ.get("SESSION_DB_DIR", "data"))
    admin_store = SqliteAdminStore(session_db_dir / "admin.sqlite3")
    admin_interface_layer = AdminInterfaceLayer(admin_store)
    fastapi_app.include_router(
        build_admin_router(
            admin_interface_layer=admin_interface_layer,
            admin_store=admin_store,
            businesses_dir=businesses_dir,
        )
    )
    fastapi_app.include_router(
        build_entities_router(
            admin_interface_layer=admin_interface_layer,
            admin_store=admin_store,
            businesses_dir=businesses_dir,
            session_db_dir=session_db_dir,
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
