"""MCP tool: re-apply categorization rules to all stored transactions.

Useful after you edit ``categories/mappings.json`` (or override via
``{data_dir}/categories.json``) and want existing rows updated.
"""

from __future__ import annotations

from datetime import date as _date
from decimal import Decimal

from personal_finance.categories import categorize, load_mappings
from personal_finance.db import get_db
from personal_finance.models import Transaction


def recategorize_all() -> dict:
    """Re-run categorization for every stored transaction.

    Reloads ``mappings.json`` first, so any edits take effect on this call.

    Returns:
        Counts of transactions inspected, updated, and a histogram of the
        resulting category distribution.
    """
    # Bust the LRU cache so edits to mappings.json are picked up.
    load_mappings.cache_clear()

    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT txn_fingerprint, institution, account_type,
                   transaction_date, description, description_clean,
                   amount, original_category, unified_category
            FROM transactions
            """
        ).fetchall()

        updates: list[tuple[str, str]] = []  # (new_cat, fingerprint)
        for fp, inst, acct, txn_date, desc, desc_clean, amt, orig_cat, current_cat in rows:
            txn = Transaction(
                txn_fingerprint=fp,
                institution=inst,
                account_type=acct,
                transaction_date=txn_date if isinstance(txn_date, _date) else _date.fromisoformat(str(txn_date)),
                description=desc,
                description_clean=desc_clean,
                amount=Decimal(str(amt)),
                original_category=orig_cat,
                source_file="",  # not used by categorize
            )
            new_cat = categorize(txn)
            if new_cat != current_cat:
                updates.append((new_cat, fp))

        for new_cat, fp in updates:
            conn.execute(
                "UPDATE transactions SET unified_category = ? WHERE txn_fingerprint = ?",
                [new_cat, fp],
            )

        histogram_rows = conn.execute(
            """
            SELECT COALESCE(unified_category, 'Uncategorized') AS cat, COUNT(*)
            FROM transactions
            GROUP BY cat
            ORDER BY COUNT(*) DESC
            """
        ).fetchall()
    finally:
        conn.close()

    return {
        "inspected": len(rows),
        "updated": len(updates),
        "histogram": [{"category": c, "count": int(n)} for c, n in histogram_rows],
    }
