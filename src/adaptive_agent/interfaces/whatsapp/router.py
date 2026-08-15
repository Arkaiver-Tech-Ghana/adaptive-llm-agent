"""GET/POST /webhook/whatsapp — Meta's verification handshake and the
inbound message webhook. Every downstream check (signature, dedupe, rate
limit, business routing, the message-length bound) lives either here or in
``InterfaceLayer``; this module's only job is translating between HTTP/
WhatsApp's wire shapes and ``InboundRequest``/``OutboundResponse``.

Always returns 200 to Meta once the signature is verified, regardless of
downstream status — a 5xx here would make Meta's retrier hammer a webhook
that our own bug (not a transient failure) caused to fail.
"""

import asyncio
import logging

from fastapi import APIRouter, Query, Request, Response
from pydantic import ValidationError

from adaptive_agent.interface_layer.contract import InboundRequest
from adaptive_agent.interface_layer.service import InterfaceLayer
from adaptive_agent.interfaces.whatsapp import outbound
from adaptive_agent.interfaces.whatsapp.payload import parse_inbound_message
from adaptive_agent.interfaces.whatsapp.signature import verify_signature

logger = logging.getLogger(__name__)

_TOO_LONG_TEXT = "Sorry, that message is too long — please keep it under 4096 characters."


def build_router(
    interface_layer: InterfaceLayer,
    verify_token: str,
    app_secret: str,
    access_token: str,
) -> APIRouter:
    router = APIRouter()

    @router.get("/webhook/whatsapp")
    def verify_webhook(
        hub_mode: str | None = Query(default=None, alias="hub.mode"),
        hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
        hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
    ) -> Response:
        if (
            hub_mode == "subscribe"
            and hub_verify_token == verify_token
            and hub_challenge is not None
        ):
            return Response(content=hub_challenge, media_type="text/plain")
        return Response(status_code=403)

    @router.post("/webhook/whatsapp")
    async def receive_webhook(request: Request) -> Response:
        raw_body = await request.body()
        signature_header = request.headers.get("X-Hub-Signature-256")
        if not verify_signature(raw_body, signature_header, app_secret):
            return Response(status_code=401)

        try:
            raw_json = await request.json()
        except ValueError:
            logger.warning("Rejected malformed JSON body on /webhook/whatsapp")
            return Response(status_code=200)

        parsed = parse_inbound_message(raw_json)
        if parsed is None:
            return Response(status_code=200)

        try:
            inbound = InboundRequest(
                business_key=parsed.phone_number_id,
                session_key=f"whatsapp:{parsed.customer_id}",
                rate_limit_key=f"whatsapp:{parsed.customer_id}",
                message_id=parsed.message_id,
                message_text=parsed.text,
            )
        except ValidationError:
            outbound.send_text_message(
                phone_number_id=parsed.phone_number_id,
                to=parsed.customer_id,
                text=_TOO_LONG_TEXT,
                access_token=access_token,
            )
            return Response(status_code=200)

        # interface_layer.process is synchronous and, via NeMo's rail checks,
        # blocking; NeMo's sync generate() also refuses to run at all when
        # called on a thread that already has an asyncio event loop running
        # (as this request handler's thread does), so this must go through
        # a worker thread rather than being awaited or called directly.
        result = await asyncio.to_thread(interface_layer.process, inbound)

        # "rate_limited"/"duplicate"/"unknown_business" -> send nothing.
        if result.status == "ok":
            if result.awaiting_confirmation:
                outbound.send_confirmation_buttons(
                    phone_number_id=parsed.phone_number_id,
                    to=parsed.customer_id,
                    text=result.text,
                    access_token=access_token,
                )
            else:
                outbound.send_text_message(
                    phone_number_id=parsed.phone_number_id,
                    to=parsed.customer_id,
                    text=result.text,
                    access_token=access_token,
                )

        return Response(status_code=200)

    return router
