# Admin identity lives outside the per-business storage keying

ADR 0003 keys all storage by `database-id + schema-identity` per Business —
every Business's data lives in its own file (`data/<business_id>.sqlite3`),
so isolation is physical, not just a `business_id` column. The Business
Admin Page (tracked in #17) needs an `admin_users` concept — owner, staff,
and a platform-operator role that by definition spans every Business for
support purposes.

Fitting that into ADR 0003's pattern would mean either giving the
platform-operator role a row in every Business's file (provisioning touches
N files for the one role that's inherently cross-cutting) or bending the
per-Business file to also hold cross-Business concerns it wasn't designed
for.

Decision: admin identity (`admin_users`, role, `business_id` mapping) and
`admin_audit_log` live in a new sibling file, `data/admin.sqlite3`, outside
the per-Business keying scheme. This is a deliberate, single, named
exception to ADR 0003 — not a departure from it. Every Business's own data
still gets its own file; only the concern that was never Business-scoped in
the first place (who is allowed to administer which Business) lives
elsewhere. Access to any given Business's data still goes through the
Admin Interface Layer, which resolves `business_id` + role from
`data/admin.sqlite3` before ever touching a per-Business file — the
exception is about where identity is stored, not about weakening
per-Business isolation.
