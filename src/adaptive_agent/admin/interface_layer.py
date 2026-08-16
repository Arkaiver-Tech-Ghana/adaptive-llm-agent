"""The Admin Interface Layer (issue #17): the single chokepoint every admin
route goes through before touching any repository or config file — mirrors
how interface_layer/service.py sits between a Frontend Adapter and the Agent
Core. Resolves identity + Business/role scope from a bearer token; the
FastAPI router never talks to AdminStore or decodes a JWT directly.

Framework-agnostic on purpose (raises typed exceptions, doesn't know about
FastAPI/HTTP) — same reasoning as InterfaceLayer.process not returning HTTP
responses.
"""

import secrets
import time
from collections.abc import Callable

from adaptive_agent.admin.auth import InvalidTokenError, decode_access_token
from adaptive_agent.admin.base import (
    AdminAuditLogEntry,
    AdminRole,
    AdminStore,
    AdminUser,
)

_CONFIRMATION_TTL_SECONDS = 5 * 60


class AdminAuthError(Exception):
    """Bearer token missing, invalid, or its subject no longer exists."""


class AdminForbiddenError(Exception):
    """Token is valid but this AdminUser's role/Business scope doesn't
    cover the requested action."""


class InvalidConfirmationTokenError(Exception):
    """confirm_token is missing, unknown, already consumed, or expired."""


class AdminInterfaceLayer:
    def __init__(
        self,
        admin_store: AdminStore,
        now_fn: Callable[[], float] = time.time,
    ) -> None:
        self._admin_store = admin_store
        self._now_fn = now_fn
        # token -> (description, expires_at). In-memory, unpersisted: this
        # is a same-session UX nicety (avoid re-typing a delete's rationale
        # on the confirming call), not a correctness requirement — losing
        # pending tokens on restart just means the client re-requests one.
        self._pending_confirmations: dict[str, tuple[str, float]] = {}

    def authorize(
        self, token: str, business_id: str | None, allowed_roles: set[AdminRole]
    ) -> AdminUser:
        try:
            claims = decode_access_token(token)
        except InvalidTokenError as exc:
            raise AdminAuthError(str(exc)) from exc

        user = self._admin_store.get_user_by_email(claims.email)
        if user is None:
            raise AdminAuthError(f"No such admin user: {claims.email}")

        if user.role not in allowed_roles:
            raise AdminForbiddenError(
                f"{user.role.value} may not perform this action"
            )

        # PLATFORM_OPERATOR is inherently cross-Business (ADR 0006) — routes
        # that admit it into allowed_roles are read-only by construction, so
        # no business_id match is required. OWNER is always scoped to
        # exactly one Business.
        if user.role != AdminRole.PLATFORM_OPERATOR and user.business_id != business_id:
            raise AdminForbiddenError(
                f"{user.email} is not scoped to Business {business_id!r}"
            )

        return user

    def record_audit(
        self,
        actor: AdminUser,
        business_id: str | None,
        action: str,
        before: str | None = None,
        after: str | None = None,
    ) -> None:
        self._admin_store.append_audit_log(
            AdminAuditLogEntry(
                actor_email=actor.email,
                business_id=business_id,
                action=action,
                before=before,
                after=after,
                timestamp=self._now_fn(),
            )
        )

    def request_confirmation(self, description: str) -> str:
        """First call on a destructive action: returns a token the caller
        must echo back (within the TTL) to actually execute it. Deterministic
        `description` text, not an LLM paraphrase — same principle as
        conversation.py's _build_confirmation_prompt."""
        token = secrets.token_urlsafe(24)
        self._pending_confirmations[token] = (description, self._now_fn() + _CONFIRMATION_TTL_SECONDS)
        return token

    def resolve_confirmation(self, confirm_token: str) -> None:
        """Second call: consumes the token if it's known and unexpired,
        raises otherwise. Always single-use — a token is popped whether or
        not it turns out to be expired, so an expired token can't be retried."""
        pending = self._pending_confirmations.pop(confirm_token, None)
        if pending is None:
            raise InvalidConfirmationTokenError("Unknown or already-used confirm_token")
        _, expires_at = pending
        if self._now_fn() > expires_at:
            raise InvalidConfirmationTokenError("confirm_token has expired")
