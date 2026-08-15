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

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

from adaptive_agent.interface_layer.dedupe import InMemoryDedupeStore
from adaptive_agent.interface_layer.rate_limiter import RateLimiter
from adaptive_agent.interface_layer.service import InterfaceLayer
from adaptive_agent.interfaces.whatsapp.registry import build_business_registry
from adaptive_agent.interfaces.whatsapp.router import build_router


def create_app() -> FastAPI:
    businesses_dir = Path(os.environ.get("BUSINESSES_DIR", "businesses"))
    business_registry = build_business_registry(businesses_dir)

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
    return fastapi_app


load_dotenv()
app = create_app()
