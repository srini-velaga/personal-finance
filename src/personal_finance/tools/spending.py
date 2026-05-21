"""Spending analysis tools. Stubs for v0 scaffold."""


def get_spending_by_category(period: str) -> dict:
    """Return spending grouped by category for a given period.

    Args:
        period: ISO period like "2026-04" (month) or "2026-Q1" (quarter).

    Returns:
        Mapping of {category: total_amount} plus a `period` echo.
    """
    return {
        "period": period,
        "categories": {},
        "_stub": "Not implemented yet — ingest pipeline pending.",
    }
