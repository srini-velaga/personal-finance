"""MCP tool: kick off ingest of a statement folder."""

from __future__ import annotations

from personal_finance.db import get_db
from personal_finance.ingest import ingest_folder as _ingest_folder


def ingest_statements(folder: str) -> dict:
    """Scan a folder recursively for CSV statements and ingest them into the local DB.

    Files are matched to bank profiles by their CSV header row, so credit and
    checking files from the same bank can live side-by-side. Files that have
    already been processed (by content hash) and individual transactions that
    are already stored (by fingerprint) are skipped automatically.

    Args:
        folder: Absolute or ``~``-expanded path to the directory containing
            statement CSVs. Searched recursively.

    Returns:
        A summary with per-file outcomes and counts of inserted vs duplicate
        transactions.
    """
    conn = get_db()
    try:
        result = _ingest_folder(folder, conn)
        return result.to_dict()
    finally:
        conn.close()
