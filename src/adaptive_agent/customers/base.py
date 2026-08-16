"""The storage-agnostic contract for Customer identity bookkeeping.

Foundational only: identity + first/last-seen, no order history or
profile fields, no new Tool. The identity substrate later features
(personalization, ADR 0001's RLS-scoped queries) attach to.
"""

from typing import Protocol


class CustomerStore(Protocol):
    def record_visit(self, customer_id: str) -> None: ...  # upsert first/last_seen
