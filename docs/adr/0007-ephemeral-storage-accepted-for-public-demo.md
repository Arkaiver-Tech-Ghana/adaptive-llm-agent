# Ephemeral storage accepted for this public repo

Self-serve signup (issue #17) creates real state on disk — a Business
Config file, a context directory, an owner row in `data/admin.sqlite3` —
but this repo's Render deploy runs on the free plan, which has no
persistent disk (see `scripts/seed_admin_owner.py`'s docstring; the disk
block was deliberately dropped from `render.yaml` for cost reasons before
this ADR). Every redeploy wipes `businesses/*/`, `data/admin.sqlite3`, and
every per-Business SQLite file — a self-serve-created Business, its owner
login, and any owner-defined tables (ADR 0008) do not survive one.

Decision: accept this for the public/demo repo, don't build around it.
Fixing it would mean either a paid Render plan with a persistent disk, or
migrating storage to a real external database — both are explicitly
deferred to a future private version of this project, which will use an
actual external database instead of file-based SQLite. This repo's job is
to demonstrate the architecture (self-serve onboarding, the generic entity
system, the Rails), not to run a durable production service. The two
already-shipped Businesses (`kampuscrave`, `hotel`) stay safe across a
redeploy via `scripts/seed_admin_owner.py`/`seed_kampuscrave_menu.py`
re-running on every boot; a self-serve-created Business has no such
reseed path and is expected to disappear on the next deploy.

See ADR 0008 for the private version's actual data-source split (a
platform-native table an owner defines, an external DB like Supabase/
Prisma with its own imposed rules, and platform-system tables) — none of
that changes this decision, since none of it is being built here either.
