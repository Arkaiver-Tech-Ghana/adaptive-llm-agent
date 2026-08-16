"""One-time (safe-to-rerun) seed script for each Business's default admin
owner account. Render's free plan has no persistent disk (Dockerfile), so
data/admin.sqlite3 is wiped every deploy — this reseeds one owner per
Business on every boot so login never breaks after a redeploy. Owner
accounts created afterward — via self-serve signup or the admin API —
don't survive a redeploy; accepted as fine for a demo-scale showcase (see
issue #17).

Only supplies data — the insert mechanics stay encapsulated in
SqliteAdminStore.upsert_user(), same convention as
scripts/seed_kampuscrave_menu.py.
"""

import os
from pathlib import Path

from adaptive_agent.admin.auth import hash_password
from adaptive_agent.admin.base import AdminRole, AdminUser
from adaptive_agent.admin.sqlite_store import SqliteAdminStore

# One (email, password) env-var pair per Business, keyed by the Business's
# uppercased business_id — e.g. ADMIN_OWNER_EMAIL_KAMPUSCRAVE /
# ADMIN_OWNER_PASSWORD_KAMPUSCRAVE. A Business with no pair set is skipped,
# not a fatal error — lets this run safely against a subset of Businesses
# (e.g. locally, with only one set).
_BUSINESS_IDS = ["kampuscrave", "hotel"]


def main() -> None:
    session_db_dir = Path(os.environ.get("SESSION_DB_DIR", "data"))
    store = SqliteAdminStore(session_db_dir / "admin.sqlite3")

    seeded = 0
    for business_id in _BUSINESS_IDS:
        prefix = business_id.upper()
        email = os.environ.get(f"ADMIN_OWNER_EMAIL_{prefix}")
        password = os.environ.get(f"ADMIN_OWNER_PASSWORD_{prefix}")
        if not email or not password:
            print(f"Skipping {business_id}: ADMIN_OWNER_EMAIL_{prefix}/PASSWORD not set")
            continue
        store.upsert_user(
            AdminUser(
                email=email,
                password_hash=hash_password(password),
                role=AdminRole.OWNER,
                business_id=business_id,
            )
        )
        seeded += 1
        print(f"Seeded owner {email!r} for {business_id}")

    print(f"Seeded {seeded} owner account(s)")


if __name__ == "__main__":
    main()
