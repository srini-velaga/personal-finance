"""DuckDB connection management.

Two ways to get a connection:
  * ``connect(path)`` — explicit, used by tests with in-memory or tmpdir paths.
  * ``get_db()`` — convenience for tool implementations; uses the configured
    data dir and initializes the schema on first call.

Connections are cheap; we open per-call rather than maintaining a pool.
DuckDB serializes writes anyway and these are short-lived analytical queries.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from personal_finance.config import db_path
from personal_finance.db.schema import init_schema


def connect(path: str | Path = ":memory:") -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection at ``path`` and initialize the schema."""
    conn = duckdb.connect(str(path))
    init_schema(conn)
    return conn


def get_db() -> duckdb.DuckDBPyConnection:
    """Return a connection to the user's configured DuckDB file."""
    return connect(db_path())
