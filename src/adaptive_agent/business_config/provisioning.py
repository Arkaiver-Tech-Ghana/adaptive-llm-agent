"""Self-serve Business provisioning (issue #17 / ADR 0007): the one place
a whole new Business — config file, context directory, owner account —
gets created end-to-end from an unauthenticated signup request, instead of
a developer hand-writing business.yaml.

Doesn't trigger a WhatsApp-registry rebuild after provisioning: a
self-serve Business defaults to a ``cli``-only frontend adapter (see
create_business_config), so it isn't WhatsApp-routable yet regardless —
rebuilding the registry here would pay the (deliberately slow, see
interfaces/whatsapp/app.py's create_app()) per-Business NeMo Rail build
cost for every already-registered Business, inside the signup request,
for zero routing benefit. The registry picks up a Business's first
``whatsapp`` adapter at the next process start, same as it does for a
hand-written Business today.
"""

import re
from pathlib import Path

from adaptive_agent.admin.auth import hash_password
from adaptive_agent.admin.base import AdminRole, AdminStore, AdminUser
from adaptive_agent.business_config.schema import (
    BusinessConfig,
    BusinessLogicConfig,
    ContextConfig,
    LLMConfig,
)
from adaptive_agent.business_config.writer import write_business_config_atomically

# business_id becomes a filesystem path segment (businesses/{id}/) and a
# SQLite filename (data/{id}.sqlite3) — a signup request is untrusted
# input controlling both, so this is an actual security boundary (path
# traversal, collisions), not just a config-load nicety. Contrast
# sql_identifiers.py, which guards identifiers that only ever come from a
# developer or an already-authenticated owner.
_BUSINESS_ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class InvalidBusinessIdError(Exception):
    pass


class BusinessAlreadyExistsError(Exception):
    pass


class OwnerEmailAlreadyExistsError(Exception):
    pass


def create_business_config(business_id: str, display_name: str) -> BusinessConfig:
    if not _BUSINESS_ID_RE.match(business_id):
        raise InvalidBusinessIdError(
            "business_id must be lowercase letters, digits, and hyphens only "
            f"(e.g. 'acme-cafe'): {business_id!r}"
        )
    return BusinessConfig(
        business_id=business_id,
        display_name=display_name,
        llm=LLMConfig(),
        context=ContextConfig(directory="context"),
        business_logic=BusinessLogicConfig(
            persona=(
                f"You are the {display_name} assistant. Update this persona from the "
                "admin Config page to describe how you should sound and what you help with."
            ),
            scope_instructions=(
                "Answer questions using the context documents and tools configured for "
                "this Business. Update this from the admin Config page."
            ),
        ),
    )


def provision_business(
    business_id: str,
    display_name: str,
    owner_email: str,
    owner_password: str,
    businesses_dir: Path,
    admin_store: AdminStore,
) -> AdminUser:
    """Creates business.yaml + an empty context/ dir + the owner account, in
    that order — a failure partway through leaves a partially-created
    Business on disk rather than a corrupted admin_users row; a re-signup
    attempt just hits BusinessAlreadyExistsError, it doesn't silently
    overwrite an existing owner.

    Checks both preconditions before touching disk at all, so a signup
    that's going to fail never leaves a half-created Business directory
    behind."""
    config = create_business_config(business_id, display_name)  # validates business_id first

    business_dir = businesses_dir / business_id
    if business_dir.exists():
        raise BusinessAlreadyExistsError(f"Business already exists: {business_id!r}")
    if admin_store.get_user_by_email(owner_email) is not None:
        raise OwnerEmailAlreadyExistsError(f"Admin user already exists: {owner_email!r}")

    business_dir.mkdir(parents=True)
    (business_dir / "context").mkdir()
    write_business_config_atomically(business_dir / "business.yaml", config.model_dump(mode="json"))

    owner = AdminUser(
        email=owner_email,
        password_hash=hash_password(owner_password),
        role=AdminRole.OWNER,
        business_id=business_id,
    )
    admin_store.upsert_user(owner)
    return owner
