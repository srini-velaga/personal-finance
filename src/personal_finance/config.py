"""Runtime config: data directory resolution and well-known paths.

Resolution order for the data dir:
  1. ``PERSONAL_FINANCE_DATA`` env var
  2. ``~/.personal-finance``

The data dir holds the DuckDB file and any user-added profiles. It is
*never* this repo's working directory — financial data must not collide
with source.
"""

from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    """Return the data directory, creating it if needed."""
    override = os.environ.get("PERSONAL_FINANCE_DATA")
    base = Path(override).expanduser() if override else Path.home() / ".personal-finance"
    base.mkdir(parents=True, exist_ok=True)
    return base


def db_path() -> Path:
    return data_dir() / "transactions.duckdb"


def user_profiles_dir() -> Path:
    """User-added profiles (in addition to the ones shipped in the package)."""
    p = data_dir() / "profiles"
    p.mkdir(parents=True, exist_ok=True)
    return p
