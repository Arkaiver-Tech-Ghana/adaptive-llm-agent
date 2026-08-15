"""InterfaceLayer: glues dedupe + rate limiting + business routing on top
of ``ConversationRuntime.handle_message`` — the layer CONTEXT.md defines
as sitting *between* a Frontend Adapter and the Agent Core. Every check
happens in order (dedupe, then rate limit, then business routing) before
``handle_message`` is ever called, so no write Tool ever fires twice and
no Customer's budget is burned by a retried delivery.
"""

from adaptive_agent.conversation import ConversationRuntime
from adaptive_agent.interface_layer.contract import InboundRequest, OutboundResponse
from adaptive_agent.interface_layer.dedupe import InMemoryDedupeStore
from adaptive_agent.interface_layer.rate_limiter import RateLimiter


class InterfaceLayer:
    def __init__(
        self,
        business_registry: dict[str, ConversationRuntime],
        rate_limiter: RateLimiter | None = None,
        dedupe_store: InMemoryDedupeStore | None = None,
    ) -> None:
        self._business_registry = business_registry
        self._rate_limiter = rate_limiter or RateLimiter()
        self._dedupe_store = dedupe_store or InMemoryDedupeStore()

    def process(self, request: InboundRequest) -> OutboundResponse:
        # Dedupe before rate-limit: a retried delivery shouldn't burn the
        # Customer's budget.
        if self._dedupe_store.is_duplicate(request.message_id):
            return OutboundResponse(status="duplicate")

        if not self._rate_limiter.allow(request.rate_limit_key):
            return OutboundResponse(status="rate_limited")

        runtime = self._business_registry.get(request.business_key)
        if runtime is None:
            return OutboundResponse(status="unknown_business")

        reply_text = runtime.handle_message(request.session_key, request.message_text)
        awaiting_confirmation = (
            runtime.session_store.get_pending_confirmation(request.session_key) is not None
        )
        return OutboundResponse(
            status="ok", text=reply_text, awaiting_confirmation=awaiting_confirmation
        )
