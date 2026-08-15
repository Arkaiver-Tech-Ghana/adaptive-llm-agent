import hashlib
import hmac

from adaptive_agent.interfaces.whatsapp.signature import verify_signature

_SECRET = "shh-its-a-secret"
_BODY = b'{"entry": [{"changes": [{"value": {}}]}]}'


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_correct_signature_is_accepted():
    header = _sign(_BODY, _SECRET)
    assert verify_signature(_BODY, header, _SECRET) is True


def test_tampered_body_is_rejected():
    header = _sign(_BODY, _SECRET)
    tampered_body = _BODY + b"tampered"
    assert verify_signature(tampered_body, header, _SECRET) is False


def test_tampered_header_is_rejected():
    header = _sign(_BODY, _SECRET)
    tampered_header = header[:-1] + ("0" if header[-1] != "0" else "1")
    assert verify_signature(_BODY, tampered_header, _SECRET) is False


def test_missing_header_is_rejected():
    assert verify_signature(_BODY, None, _SECRET) is False


def test_header_without_sha256_prefix_is_rejected():
    assert verify_signature(_BODY, "not-a-real-signature", _SECRET) is False


def test_wrong_secret_is_rejected():
    header = _sign(_BODY, "a-different-secret")
    assert verify_signature(_BODY, header, _SECRET) is False
