"""Spending analysis tools + the canonical period parser used by other tools."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import duckdb

from personal_finance.db import get_db


def _last_day_of_month(year: int, month: int) -> date:
    """Return the last calendar day of ``year``/``month``."""
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1) - timedelta(days=1)


def _parse_period(
    period: str,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> tuple[date, date]:
    """Resolve a period string to an inclusive ``(start, end)`` date range.

    Accepted formats (case-insensitive):

    *Calendar windows:*
      * ``"2026-04"``        — calendar month
      * ``"2026-Q2"``        — calendar quarter (Q1..Q4)
      * ``"2026"``           — full calendar year
      * ``"2026-04-15"``     — a single ISO date (start == end)

    *Rolling / relative windows (no DB needed):*
      * ``"ytd"``            — Jan 1 of the current year through today
      * ``"last_30_days"``   — 30-day rolling window ending today
      * ``"last_90_days"``   — 90-day rolling window ending today
      * ``"last_12_months"`` — 365-day rolling window ending today

    *DB-relative (``conn`` required):*
      * ``"all"`` / ``"lifetime"`` — min/max of ``transaction_date`` in the DB.
        If the DB is empty, returns ``(today, today)`` so the response shape
        stays stable.

    Args:
        period: One of the patterns above.
        conn: Optional DuckDB connection. Required only for ``"all"``/``"lifetime"``.

    Raises:
        ValueError: For unrecognized patterns, invalid quarter numbers, or a
            DB-relative pattern called without ``conn``.
    """
    p = period.strip().lower()
    today = date.today()

    # ---------- DB-relative ----------
    if p in ("all", "lifetime"):
        if conn is None:
            raise ValueError(
                f"period={period!r} needs a DB connection; pass conn=..."
            )
        row = conn.execute(
            "SELECT MIN(transaction_date), MAX(transaction_date) FROM transactions"
        ).fetchone()
        start, end = (row[0], row[1]) if row else (None, None)
        if start is None or end is None:
            return today, today
        return start, end

    # ---------- rolling windows ----------
    if p == "ytd":
        return date(today.year, 1, 1), today

    if p == "last_30_days":
        return today - timedelta(days=29), today
    if p == "last_90_days":
        return today - timedelta(days=89), today
    if p == "last_12_months":
        return today - timedelta(days=365), today

    # ---------- calendar patterns ----------
    # YYYY-Qn
    if len(p) == 7 and p[4] == "-" and p[5] == "q":
        year = int(p[:4])
        q = int(p[6])
        if q not in (1, 2, 3, 4):
            raise ValueError(f"invalid quarter: {period!r}")
        start_month = 3 * (q - 1) + 1
        return date(year, start_month, 1), _last_day_of_month(year, start_month + 2)

    # YYYY-MM
    if len(p) == 7 and p[4] == "-":
        year, month = int(p[:4]), int(p[5:7])
        return date(year, month, 1), _last_day_of_month(year, month)

    # YYYY
    if len(p) == 4 and p.isdigit():
        year = int(p)
        return date(year, 1, 1), date(year, 12, 31)

    # ISO date (single-day window)
    try:
        parsed = datetime.strptime(period, "%Y-%m-%d").date()
        return parsed, parsed
    except ValueError as e:
        raise ValueError(f"unrecognized period: {period!r}") from e


def get_spending_by_category(period: str, account_type: str | None = None) -> dict:
    """Return spending grouped by category for a given period.

    Sums only **expenses** (positive amounts in the unified sign convention).
    Uses ``unified_category`` if present, otherwise falls back to
    ``original_category``, otherwise ``"Uncategorized"``.

    Args:
        period: Any value accepted by ``_parse_period``:
            ``"YYYY-MM"``, ``"YYYY-Qn"``, ``"YYYY"``, ``"YYYY-MM-DD"``,
            ``"ytd"``, ``"last_30_days"``, ``"last_90_days"``,
            ``"last_12_months"``, or ``"all"`` / ``"lifetime"``.
        account_type: Optional filter — ``"credit_card"``, ``"checking"``,
            ``"savings"``. Omit to include all accounts.

    Returns:
        ``{"period": ..., "start": ..., "end": ..., "categories": [...],
           "total_expense": N}`` where ``categories`` is a list of
        ``{"category": str, "amount": float, "txn_count": int}`` sorted
        descending by amount.
    """
    conn = get_db()
    try:
        start, end = _parse_period(period, conn=conn)

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
