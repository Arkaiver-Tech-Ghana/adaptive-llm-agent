"""The storage-agnostic contract for admin identity + audit (issue #17,
ADR 0006). ``AdminStore`` is deliberately separate from ``CustomerStore``/
``SessionStore``: it's platform-wide (one ``data/admin.sqlite3``, not one
file per Business — see ADR 0006), and the ``platform_operator`` role is
inherently cross-Business, which is the whole reason it can't live inside
any single Business's per-file storage (ADR 0003).
"""

from enum import Enum
from typing import Protocol

from pydantic import BaseModel


class AdminRole(str, Enum):
    OWNER = "owner"
    STAFF = "staff"
    PLATFORM_OPERATOR = "platform_operator"


class AdminUser(BaseModel):
    email: str
    password_hash: str
    role: AdminRole
    # None only for PLATFORM_OPERATOR — every OWNER/STAFF user is scoped to
    # exactly one Business (issue #17's role table).
    business_id: str | None = None


class AdminAuditLogEntry(BaseModel):
    # None until persisted; the store assigns the real id on append (mirrors
    # how a DB-generated rowid works — callers never invent their own).
    id: int | None = None
    actor_email: str
    business_id: str | None
    action: str
    before: str | None = None
    after: str | None = None
    timestamp: float


class AdminStore(Protocol):
    def get_user_by_email(self, email: str) -> AdminUser | None: ...
    def upsert_user(self, user: AdminUser) -> None: ...
    def list_users_for_business(self, business_id: str) -> list[AdminUser]: ...
    def append_audit_log(self, entry: AdminAuditLogEntry) -> None: ...
    # business_id=None returns every Business's entries — only meant to be
    # called after the caller has already confirmed PLATFORM_OPERATOR scope.
    def list_audit_log(self, business_id: str | None) -> list[AdminAuditLogEntry]: ...
