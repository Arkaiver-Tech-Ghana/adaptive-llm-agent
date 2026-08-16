"""Shared SQL-identifier validation. Table/column names get interpolated
directly into query strings (sqlite3 can't bind identifiers with ``?``), so
this is the actual injection guard wherever a name comes from outside a
literal in this codebase (Business Config, the entity/table system's owner-
supplied ``TableDef``). Row/cell values never go through this — they stay
parameter-bound.
"""

import re

SQL_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_identifier(value: str, error_cls: type[Exception]) -> str:
    if not SQL_IDENTIFIER_RE.match(value):
        raise error_cls(f"Not a valid SQL identifier: {value!r}")
    return value
