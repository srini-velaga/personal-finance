"""MCP tool: query transactions with simple filters.

Returns plain JSON-shaped dicts so the agent can reason over them directly
and Claude Desktop can auto-render charts from any tabular structure.
"""

from __future__ import annotations

from datetime import date as _date
from datetime import datetime
from decimal import Decimal

from personal_finance.db import get_db


def _to_date(s: str | None) -> _date | None:
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d").date()


def get_transactions(
    start_date: str | None = None,
    end_date: str | None = None,
    institution: str | None = None,
    account_type: str | None = None,
    category: str | None = None,
    description_contains: str | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    limit: int = 200,
) -> dict:
    """Query stored transactions with optional filters.

    All filters are AND-combined. Dates are ISO ``YYYY-MM-DD``. Amount filters
    use the unified sign convention (positive = expense). ``category`` matches
    against ``unified_category`` first and falls back to ``original_category``
    if the unified taxonomy isn't populated yet.

    Args:
        start_date: Inclusive lower bound on ``transaction_date``.
        end_date: Inclusive upper bound on ``transaction_date``.
        institution: e.g. ``"chase"``.
        account_type: ``"credit_card"`` | ``"checking"`` | ``"savings"``.
        category: Matches either unified or original category (case-insensitive).
        description_contains: Substring match on description (case-insensitive).
        min_amount: Filter amount >= this value (in unified sign).
        max_amount: Filter amount <= this value.
        limit: Max rows to return. Default 200, capped at 5000.

    Returns:
        ``{"count": N, "transactions": [...]}`` where each transaction is a
        flat dict with all the columns.
    """
    limit = max(1, min(limit, 5000))
    clauses: list[str] = []
    params: list = []

    if start_date:
        clauses.append("transaction_date >= ?")
        params.append(_to_date(start_date))
    if end_date:
        clauses.append("transaction_date <= ?")
        params.append(_to_date(end_date))
    if institution:
        clauses.append("LOWER(institution) = LOWER(?)")
        params.append(institution)
    if account_type:
        clauses.append("LOWER(account_type) = LOWER(?)")
        params.append(account_type)
    if category:
        clauses.append("(LOWER(unified_category) = LOWER(?) OR LOWER(original_category) = LOWER(?))")
        params.extend([category, category])
    if description_contains:
        clauses.append("LOWER(description) LIKE LOWER(?)")
        params.append(f"%{description_contains}%")
    if min_amount is not None:
        clauses.append("amount >= ?")
        params.append(Decimal(str(min_amount)))
    if max_amount is not None:
        clauses.append("amount <= ?")
        params.append(Decimal(str(max_amount)))

    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT
            txn_fingerprint, institution, account_type,
            transaction_date, post_date,
            description, amount,
            original_category, unified_category,
            source_file
        FROM transactions
        {where}
        ORDER BY transaction_date DESC, txn_fingerprint
        LIMIT {limit}
    """

    conn = get_db()
    try:
        rows = conn.execute(sql, params).fetchall()
        cols = [d[0] for d in conn.description]
    finally:
        conn.close()

    transactions = []
    for row in rows:
        rec = dict(zip(cols, row, strict=True))
        # Make Decimals and dates JSON-friendly.
        if rec["amount"] is not None:
            rec["amount"] = float(rec["amount"])
        for k in ("transaction_date", "post_date"):
            if rec[k] is not None:
                rec[k] = rec[k].isoformat()
        transactions.append(rec)

    return {"count": len(transactions), "transactions": transactions}
