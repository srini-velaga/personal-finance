"""Spending analysis tools."""

from __future__ import annotations

from datetime import date, datetime

from personal_finance.db import get_db


def _parse_period(period: str) -> tuple[date, date]:
    """Resolve a period string to inclusive ``(start, end)`` dates.

    Accepted formats:
      * ``"2026-04"``   — calendar month
      * ``"2026-Q2"``   — calendar quarter (Q1..Q4)
      * ``"2026"``      — full calendar year
    """
    p = period.strip().upper()

    if len(p) == 7 and p[4] == "-" and p[5] == "Q":
        year = int(p[:4])
        q = int(p[6])
        if q not in (1, 2, 3, 4):
            raise ValueError(f"invalid quarter: {period}")
        start_month = 3 * (q - 1) + 1
        end_month = start_month + 2
        start = date(year, start_month, 1)
        # last day of end_month
        if end_month == 12:
            end = date(year, 12, 31)
        else:
            end = date(year, end_month + 1, 1).fromordinal(
                date(year, end_month + 1, 1).toordinal() - 1
            )
        return start, end

    if len(p) == 7 and p[4] == "-":
        year, month = int(p[:4]), int(p[5:7])
        start = date(year, month, 1)
        if month == 12:
            end = date(year, 12, 31)
        else:
            end = date(year, month + 1, 1).fromordinal(
                date(year, month + 1, 1).toordinal() - 1
            )
        return start, end

    if len(p) == 4 and p.isdigit():
        year = int(p)
        return date(year, 1, 1), date(year, 12, 31)

    # Fallback: try ISO date
    parsed = datetime.strptime(period, "%Y-%m-%d").date()
    return parsed, parsed


def get_spending_by_category(period: str, account_type: str | None = None) -> dict:
    """Return spending grouped by category for a given period.

    Sums only **expenses** (positive amounts in the unified sign convention).
    Uses ``unified_category`` if present, otherwise falls back to
    ``original_category``, otherwise ``"Uncategorized"``.

    Args:
        period: ``"YYYY-MM"`` for a month, ``"YYYY-Qn"`` for a quarter, or
            ``"YYYY"`` for a full year.
        account_type: Optional filter — ``"credit_card"``, ``"checking"``,
            ``"savings"``. Omit to include all accounts.

    Returns:
        ``{"period": ..., "start": ..., "end": ..., "categories": [...],
           "total_expense": N}`` where ``categories`` is a list of
        ``{"category": str, "amount": float, "txn_count": int}`` sorted
        descending by amount.
    """
    start, end = _parse_period(period)

    clauses = ["transaction_date BETWEEN ? AND ?", "amount > 0"]
    params: list = [start, end]
    if account_type:
        clauses.append("LOWER(account_type) = LOWER(?)")
        params.append(account_type)

    sql = f"""
        SELECT
            COALESCE(unified_category, original_category, 'Uncategorized') AS category,
            SUM(amount) AS total,
            COUNT(*) AS txn_count
        FROM transactions
        WHERE {' AND '.join(clauses)}
        GROUP BY category
        ORDER BY total DESC
    """

    conn = get_db()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    categories = [
        {"category": cat, "amount": float(total), "txn_count": int(cnt)}
        for cat, total, cnt in rows
    ]
    total_expense = sum(c["amount"] for c in categories)

    return {
        "period": period,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "account_type": account_type,
        "total_expense": total_expense,
        "categories": categories,
    }
