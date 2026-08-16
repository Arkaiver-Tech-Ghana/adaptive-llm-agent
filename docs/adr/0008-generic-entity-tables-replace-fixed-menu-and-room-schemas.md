# Generic entity tables replace fixed Menu/Room schemas

The admin product turned out to be "any business owner defines their own
data," not "a developer adds a new fixed-schema repository class per
Business type." `RoomRepository`/`MenuRepository`'s SQLite implementations
let a Business Config rename a table/its columns (`storage.table`/
`.columns`), but the *set* of fields was still hardcoded per Python class —
onboarding a Business with a genuinely different data shape meant writing a
new repository, which is exactly the per-business-type coupling this
project's core invariant rules out.

Decision: replace `rooms/` and `MenuRepository`'s SQLite backend with a
generic entity/table system (`entities/`) — a Business owner defines their
own `TableDef` (name, columns, types: text/number/boolean) through the
admin UI, and `SqliteEntityRepository` stores it against a
`__qantonic_tables__` metadata table per Business SQLite file, alongside
the table itself. `entities.EntityRepository` is a Protocol, `menu/base.py`
(the `MenuRepository` Protocol + `MenuItem` model) is unchanged —
`tools/kampuscrave_provider.py`, the one live chat-facing demo path this
touches, still depends only on that Protocol. `EntityBackedMenuRepository`
implements it by delegating to whichever table carries
`tool_linked="sqlite_menu"`, so the swap is invisible above the repository
layer.

This supersedes ADR 0003's `storage.table`/`.columns` fields for the
tables this system manages — they're left in the schema (not removed) for
now since existing Business Config files still validate against them, but
new tables go through `entities.TableDef`, not Business Config.

## `tool_linked`: how a chat-facing Tool finds its table

A table optionally carries `tool_linked: str | None` — the same string a
Business Config's `tool_provider` field already names (e.g.
`"sqlite_menu"`). `tools/registry.py` resolves a Business's Tool provider
by scanning `SqliteEntityRepository.list_tables()` for the one carrying
that string, instead of a hardcoded table name — the same "provider *type*,
not per-business hardcoding" pattern the tool registry already uses (see
`feature/generic-tool-provider-selection`, #29). `create_table()` enforces
a required-column superset for a claimed `tool_linked` type (e.g.
`sqlite_menu` requires `name`/`category`/`price`/`stock_quantity`) and
rejects a second table claiming the same type — a Tool needs exactly one
unambiguous table behind it.

## Future extensibility (not built now)

The future private version adds data sources this ADR's `EntityRepository`
Protocol needs to keep room for without a rewrite:

- **External DB-backed tables** (e.g. Supabase/Prisma) — schema fixed
  externally, the backend only CRUDs through it, subject to whatever rules
  the external system already imposes. A future
  `SupabaseEntityRepository` (or similar) implements the same
  `EntityRepository` Protocol `SqliteEntityRepository` implements today, so
  `entities_router.py` and `EntityBackedMenuRepository` don't change.
- **Platform-system tables** (identity/device data) — never owner-editable,
  already outside the owner-facing Database UI today (this system only
  ever lists tables an owner created).
- **An owner-added policy/rules layer** on top of whatever rules a data
  source itself imposes (rate limits, per-user-type restrictions on
  data/tool access), and **per-frontend-adapter tool-access scoping** (the
  same agent running on multiple platforms with different rights). Neither
  is designed yet — expected to wrap/compose with `EntityRepository` and
  the tool registry rather than require reshaping `TableDef`.

See also ADR 0007 (ephemeral storage accepted for this public repo).
