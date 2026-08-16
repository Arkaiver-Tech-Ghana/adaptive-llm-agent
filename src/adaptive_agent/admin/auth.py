"""Password hashing + JWT issue/verify for Business Admin auth.

Deliberately not built on the generic ``AuthProvider`` Protocol
(auth/base.py) — same precedent as ADR 0005 (the WhatsApp signature check):
email+password -> JWT doesn't fit ``authenticate(credential: str) -> bool``
any better than an HMAC signature check did, so this stays its own module
instead of stretching that Protocol to cover two unrelated shapes.
"""

import os
import time

import bcrypt
import jwt
from pydantic import BaseModel

from adaptive_agent.admin.base import AdminRole, AdminUser

_ALGORITHM = "HS256"
_TOKEN_TTL_SECONDS = 24 * 60 * 60


class AdminTokenClaims(BaseModel):
    email: str
    role: AdminRole
    business_id: str | None


class InvalidTokenError(Exception):
    """Raised when a bearer token is missing, expired, tampered with, or
    otherwise fails to decode — the router turns this into a 401."""


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), password_hash.encode())


def _secret() -> str:
    # No default: an admin JWT signed with a guessable/shared fallback
    # secret would defeat the whole point of auth. Fail closed at call
    # time rather than silently signing with something insecure.
    return os.environ["ADMIN_JWT_SECRET"]


def create_access_token(user: AdminUser, now_fn=time.time) -> str:
    now = now_fn()
    payload = {
        "email": user.email,
        "role": user.role.value,
        "business_id": user.business_id,
        "iat": now,
        "exp": now + _TOKEN_TTL_SECONDS,
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGORITHM)


def decode_access_token(token: str) -> AdminTokenClaims:
    try:
        payload = jwt.decode(token, _secret(), algorithms=[_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
    return AdminTokenClaims(
        email=payload["email"],
        role=AdminRole(payload["role"]),
        business_id=payload.get("business_id"),
    )
