# TODO

- Build Excalidraw diagrams of the system + subsystems (rails flow, agent
  core, business config swap, session/confirmation state machine) to help
  explain the architecture visually.
- Session data backup/analytics: the file-per-Business SQLite layout
  (`session/sqlite_store.py`) makes this cheap mechanically later — WAL
  mode supports online backup without stopping the process
  (`sqlite3.Connection.backup()` or a scheduled `.backup` copy), no
  architecture change needed. What's still open isn't mechanics, it's
  governance: "by us" (cross-Business access, e.g. platform-level
  analytics) is a different boundary than "by the business" (a Business
  reading only its own Customers' data) — ADR 0001 (RLS by default) only
  settles Customer-to-Customer isolation, not this. Design-for-later, like
  the Business Admin UI P2 item — no code, no schedule job, no
  access-control layer yet.
