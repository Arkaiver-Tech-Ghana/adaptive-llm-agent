"""Verifies WhatsApp Cloud API's ``X-Hub-Signature-256`` header: HMAC-SHA256
over the raw request body, keyed by the Meta App Secret. Checked before any
payload parsing — an unsigned/tampered request never reaches ``payload.py``.
"""

import hashlib
import hmac

_SIGNATURE_PREFIX = "sha256="


def verify_signature(raw_body: bytes, header_value: str | None, app_secret: str) -> bool:
    if not header_value or not header_value.startswith(_SIGNATURE_PREFIX):
        return False

    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    provided = header_value[len(_SIGNATURE_PREFIX) :]
    return hmac.compare_digest(expected, provided)
