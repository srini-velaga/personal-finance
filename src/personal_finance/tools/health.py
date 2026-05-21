"""Health / freshness tools."""

from __future__ import annotations

from personal_finance import __version__
from personal_finance.db import get_db


def get_data_freshness() -> dict:
    """Report the state of the local data store.

    Returns:
        Server version, total transaction count, count of distinct
        institution+account_type combinations, and the most recent
        transaction date per account.
    """
    conn = get_db()
    try:
        total = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        rows = conn.execute(
            """
            SELECT
                institution,
                account_type,
                COUNT(*) AS txn_count,
                MAX(transaction_date) AS latest_transaction,
                MAX(ingested_at) AS latest_ingest
            FROM transactions
            GROUP BY institution, account_type
            ORDER BY institution, account_type
            """
        ).fetchall()
        files_processed = conn.execute("SELECT COUNT(*) FROM processing_log").fetchone()[0]
    finally:
        conn.close()

    accounts = [
        {
            "institution": inst,
            "account_type": acct,
            "txn_count": int(count),
            "latest_transaction": latest_txn.isoformat() if latest_txn else None,
            "latest_ingest": latest_ing.isoformat() if latest_ing else None,
        }
        for inst, acct, count, latest_txn, latest_ing in rows
    ]

    return {
        "server_version": __version__,
        "transaction_count": int(total),
        "files_processed": int(files_processed),
        "accounts": accounts,
    }
