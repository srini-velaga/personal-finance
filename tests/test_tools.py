"""Tests for the MCP tools — verify they query the DB correctly.

We monkeypatch ``get_db`` to point at a tmp DuckDB so the user's real data
dir is never touched during testing.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from personal_finance.db import connect
from personal_finance.ingest import ingest_folder, load_profiles

FIXTURE = Path(__file__).parent / "fixtures" / "chase_credit_sample.csv"


@pytest.fixture
def populated_db(tmp_path, monkeypatch):
    """A DuckDB pre-loaded with the Chase fixture, wired into the tools layer."""
    db_file = tmp_path / "test.duckdb"

    folder = tmp_path / "statements"
    folder.mkdir()
    shutil.copy(FIXTURE, folder / "chase_april.csv")

    conn = connect(db_file)
    ingest_folder(folder, conn, profiles=load_profiles())
    conn.close()

    # Redirect every tool's get_db() to our tmp file.
    def _get_db():
        return connect(db_file)

    for module in ("transactions", "spending", "health"):
        monkeypatch.setattr(f"personal_finance.tools.{module}.get_db", _get_db)

    return db_file


def test_get_transactions_returns_all(populated_db):
    from personal_finance.tools.transactions import get_transactions
    result = get_transactions()
    assert result["count"] == 8
    # Ordered DESC by date.
    dates = [t["transaction_date"] for t in result["transactions"]]
    assert dates == sorted(dates, reverse=True)


def test_get_transactions_filters_by_date_and_category(populated_db):
    from personal_finance.tools.transactions import get_transactions
    result = get_transactions(
        start_date="2026-04-05",
        end_date="2026-04-15",
        category="Groceries",
    )
    # Only Whole Foods on 04-05 is in range AND category Groceries.
    assert result["count"] == 1
    assert "WHOLE FOODS" in result["transactions"][0]["description"].upper()


def test_get_transactions_amount_filter(populated_db):
    from personal_finance.tools.transactions import get_transactions
    # min_amount=50 → only expenses >= $50 (Whole Foods 83.42, Trader Joe 61.22)
    # Payment of -500 is excluded (it's negative).
    result = get_transactions(min_amount=50)
    assert result["count"] == 2
    amounts = sorted(t["amount"] for t in result["transactions"])
    assert amounts == [61.22, 83.42]


def test_get_spending_by_category_monthly(populated_db):
    from personal_finance.tools.spending import get_spending_by_category
    result = get_spending_by_category("2026-04")

    assert result["start"] == "2026-04-01"
    assert result["end"] == "2026-04-30"

    # Expenses only — payment row is income, excluded.
    cats = {c["category"]: c["amount"] for c in result["categories"]}
    assert "Food & Drink" in cats
    assert cats["Groceries"] == pytest.approx(83.42 + 61.22)
    assert "Payment" not in cats and "" not in cats

    total = sum(c["amount"] for c in result["categories"])
    assert result["total_expense"] == pytest.approx(total)


def test_get_spending_by_category_quarterly(populated_db):
    from personal_finance.tools.spending import get_spending_by_category
    result = get_spending_by_category("2026-Q2")
    assert result["start"] == "2026-04-01"
    assert result["end"] == "2026-06-30"
    # All 8 fixture rows are in Q2.
    total_count = sum(c["txn_count"] for c in result["categories"])
    assert total_count == 7  # 8 minus the payment


def test_get_data_freshness(populated_db):
    from personal_finance.tools.health import get_data_freshness
    result = get_data_freshness()
    assert result["transaction_count"] == 8
    assert result["files_processed"] == 1
    assert len(result["accounts"]) == 1
    acct = result["accounts"][0]
    assert acct["institution"] == "chase"
    assert acct["account_type"] == "credit_card"
    assert acct["txn_count"] == 8
    assert acct["latest_transaction"] == "2026-04-28"
