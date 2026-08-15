# WhatsApp's webhook signature check lives in the adapter, not behind AuthProvider

`auth/base.py`'s `AuthProvider` Protocol models a single opaque credential:
`authenticate(credential: str) -> bool`. WhatsApp Cloud API's webhook
verification is a different shape entirely — HMAC-SHA256 over the raw
request body, keyed by the Meta App Secret (`X-Hub-Signature-256`), plus a
separate one-time verify-token handshake on `GET /webhook/whatsapp`.
Neither is "here's a credential, tell me if it's valid."

Forcing the webhook check through `AuthProvider` would mean either
smuggling the raw body and header through the single `credential: str`
parameter (an artificial fit that defeats the Protocol's own shape) or
widening `AuthProvider` itself to accommodate one frontend's transport
detail — which would leak WhatsApp-specific concerns into an axis meant to
stay frontend-agnostic.

Decision: treat the verify-token handshake and the HMAC signature check as
transport-level concerns living in `interfaces/whatsapp/signature.py` and
`router.py` themselves, not behind `AuthProvider`. They still satisfy the
PRD's "basic account/auth validation" acceptance criterion directly — they
just don't need the `AuthProvider` indirection to do it. `AuthConfig.type`
stays `"none"` in both `business.yaml`s; nothing here is a stand-in for a
real per-Customer auth axis, which remains `AuthProvider`'s job whenever a
Business actually needs one.
