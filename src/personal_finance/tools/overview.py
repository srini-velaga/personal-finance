"""MCP tool: a single 'glance' snapshot of the user's finances.

Returns several structured sub-tables in one response. Claude Desktop's
client renders tabular results as charts automatically, so this tool is
effectively a dashboard without us writing any rendering code.

Cashflow math:
  * ``total_expense`` = sum of positive amounts, **excluding** unified
    categories ``Payments & Credits`` and ``Transfers``. Credit-card bill
    payments and internal account moves aren't real expenses.
  * ``total_income`` = sum of |amount| for negative amounts, **with the
    same exclusions**. So a credit-card payment doesn't get double-counted
    as income.
  * ``net_cashflow`` = ``total_income - total_expense``.
  * ``savings_rate`` = net / income (only computed when income > 0).
"""

from __future__ import annotations

from datetime import date

from personal_finance.db import get_db
from personal_finance.tools.spending import _parse_period

_EXCLUDED_FROM_CASHFLOW = ("Payments & Credits", "Transfers")


def _resolve_period(period: str | None, conn) -> tuple[str, date, date]:
    """Return ``(label, start, end)``. Defaults to the most recent month with data."""
    if period is not None:
        start, end = _parse_period(period)
        return period, start, end

    row = conn.execute(
        "SELECT MAX(transaction_date) FROM transactions"
    ).fetchone()
    latest: date | None = row[0] if row else None
    if latest is None:
        # No data yet — fall back to today's month so the response shape is stable.
        today = date.today()
        period = f"{today.year:04d}-{today.month:02d}"
    else:
        period = f"{latest.year:04d}-{latest.month:02d}"
    start, end = _parse_period(period)
    return period, start, end


def get_financial_overview(period: str | None = None, top_n: int = 5) -> dict:
    """Return a one-glance snapshot of finances for a given period.

    Args:
        period: ``"YYYY-MM"``, ``"YYYY-Qn"``, or ``"YYYY"``. If omitted,
            defaults to the **most recent month that has data** so the
            response is never empty when transactions exist.
        top_n: How many rows to return in the top-categories and
            top-merchants lists. Clamped to [1, 25].

    Returns:
        A dict with ``period`` info, a ``headline`` block (total expense,
        total income, net cashflow, savings rate, transaction count), and
        four sub-tables: ``top_categories``, ``top_merchants``,
        ``recent_transactions``, ``accounts``. Each sub-table is a flat
        list of dicts suitable for chart rendering.
    """
    top_n = max(1, min(top_n, 25))

    conn = get_db()
    try:
        period_label, start, end = _resolve_period(period, conn)

        # ---------- headline cashflow ----------
        excl_placeholders = ",".join(["?"] * len(_EXCLUDED_FROM_CASHFLOW))
        headline_row = conn.execute(
            f"""
            SELECT
                COALESCE(SUM(CASE
                    WHEN amount > 0 AND COALESCE(unified_category, '') NOT IN ({excl_placeholders})
                    THEN amount ELSE 0 END), 0) AS total_expense,
                COALESCE(SUM(CASE
                    WHEN amount < 0 AND COALESCE(unified_category, '') NOT IN ({excl_placeholders})
                    THEN -amount ELSE 0 END), 0) AS total_income,
                COUNT(*) AS txn_count
            FROM transactions
            WHERE transaction_date BETWEEN ? AND ?
            """,
            [*_EXCLUDED_FROM_CASHFLOW, *_EXCLUDED_FROM_CASHFLOW, start, end],
        ).fetchone()
        total_expense = float(headline_row[0])
        total_income = float(headline_row[1])
        txn_count = int(headline_row[2])
        net = total_income - total_expense
        savings_rate = (net / total_income) if total_income > 0 else None

        # ---------- top categories (expenses only) ----------
        top_cats = conn.execute(
            f"""
            SELECT
                COALESCE(unified_category, 'Uncategorized') AS category,
                SUM(amount) AS total,
                COUNT(*) AS txn_count
            FROM transactions
            WHERE transaction_date BETWEEN ? AND ?
              AND amount > 0
              AND COALESCE(unified_category, '') NOT IN ({excl_placeholders})
            GROUP BY category
            ORDER BY total DESC
            LIMIT {top_n}
            """,
            [start, end, *_EXCLUDED_FROM_CASHFLOW],
        ).fetchall()

        # ---------- top merchants (expenses only) ----------
        top_merch = conn.execute(
            f"""
            SELECT
                description_clean AS merchant,
                SUM(amount) AS total,
                COUNT(*) AS txn_count
            FROM transactions
            WHERE transaction_date BETWEEN ? AND ?
              AND amount > 0
              AND COALESCE(unified_category, '') NOT IN ({excl_placeholders})
            GROUP BY description_clean
            ORDER BY total DESC
            LIMIT {top_n}
            """,
            [start, end, *_EXCLUDED_FROM_CASHFLOW],
        ).fetchall()

        # ---------- recent transactions ----------
        recent = conn.execute(
            """
            SELECT transaction_date, description, amount,
                   COALESCE(unified_category, 'Uncategorized') AS category,
                   institution, account_type
            FROM transactions
            WHERE transaction_date BETWEEN ? AND ?
            ORDER BY transaction_date DESC, txn_fingerprint
            LIMIT 10
            """,
            [start, end],
        ).fetchall()

        # ---------- per-account activity in this period ----------
        # ``debits`` is raw spend in the account; ``credits`` is raw
        # incoming/refund (includes credit-card bill payments). The headline
        # cashflow above applies the Payments & Credits / Transfers exclusion
        # to derive real income/expense; this block is the raw statement view.
        accounts = conn.execute(
            """
            SELECT
                institution,
                account_type,
                COUNT(*) AS txn_count,
                COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) AS debits,
                COALESCE(SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END), 0) AS credits,
                MAX(transaction_date) AS latest_transaction
            FROM transactions
            WHERE transaction_date BETWEEN ? AND ?
            GROUP BY institution, account_type
            ORDER BY institution, account_type
            """,
            [start, end],
        ).fetchall()
    finally:
        conn.close()

    return {
        "period": period_label,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "headline": {
            "total_expense": round(total_expense, 2),
            "total_income": round(total_income, 2),
            "net_cashflow": round(net, 2),
            "savings_rate": round(savings_rate, 4) if savings_rate is not None else None,
            "transaction_count": txn_count,
        },
        "top_categories": [
            {"category": cat, "amount": round(float(total), 2), "txn_count": int(cnt)}
            for cat, total, cnt in top_cats
        ],
        "top_merchants": [
            {"merchant": m, "amount": round(float(total), 2), "txn_count": int(cnt)}
            for m, total, cnt in top_merch
        ],
        "recent_transactions": [
            {
                "date": txn_date.isoformat(),
                "description": desc,
                "amount": round(float(amt), 2),
                "category": cat,
                "institution": inst,
                "account_type": acct,
            }
            for txn_date, desc, amt, cat, inst, acct in recent
        ],
        "accounts": [
            {
                "institution": inst,
                "account_type": acct,
                "txn_count": int(cnt),
                "debits": round(float(debits), 2),
                "credits": round(float(credits), 2),
                "latest_transaction": latest.isoformat() if latest else None,
            }
            for inst, acct, cnt, debits, credits, latest in accounts
        ],
    }
