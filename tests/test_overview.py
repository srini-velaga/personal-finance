"""Tests for the get_financial_overview dashboard tool."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from personal_finance.db import connect
from personal_finance.ingest import ingest_folder, load_profiles

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def multi_bank_db(tmp_path, monkeypatch):
    """Ingest Chase + Amex + Discover + Wells Fargo fixtures into a tmp DB."""
    db_file = tmp_path / "test.duckdb"
    folder = tmp_path / "stmt"
    folder.mkdir()
    shutil.copy(FIXTURES / "chase_credit_sample.csv", folder / "chase.csv")
    shutil.copy(FIXTURES / "amex_credit_sample.csv", folder / "amex.csv")
    shutil.copy(FIXTURES / "discover_credit_sample.csv", folder / "discover.csv")
    shutil.copy(FIXTURES / "wells_fargo_credit_sample.csv", folder / "wf.csv")

    conn = connect(db_file)
    ingest_folder(folder, conn, profiles=load_profiles())
    conn.close()

    def _get_db():
        return connect(db_file)

    monkeypatch.setattr("personal_finance.tools.overview.get_db", _get_db)
    return db_file


def test_overview_default_is_last_12_months(multi_bank_db):
    """No period → rolling 365-day window ending today.

    This is the polish-pass v0.6 change: previously the default was
    "most recent month with data" which gave a sparse view when the
    latest statement was mid-month. Last 12 months is time-stable.
    """
    from datetime import date, timedelta

    from personal_finance.tools.overview import get_financial_overview
    result = get_financial_overview()
    assert result["period"] == "last_12_months"

    today = date.today()
    assert result["end"] == today.isoformat()
    assert result["start"] == (today - timedelta(days=365)).isoformat()


def test_overview_headline_excludes_payments_from_income(multi_bank_db):
    from personal_finance.tools.overview import get_financial_overview
    result = get_financial_overview("2026-04")

    headline = result["headline"]
    # The Chase ($500), Amex ($1250), Discover ($1425.50), WF ($1450) payments
    # are all credit-card payments (unified_category = "Payments & Credits") and
    # MUST NOT be counted as income.
    assert headline["total_income"] == 0
    # Net is just -expense when income is zero.
    assert headline["net_cashflow"] == -headline["total_expense"]
    # No savings rate when there's no income.
    assert headline["savings_rate"] is None


def test_overview_returns_all_sub_tables(multi_bank_db):
    from personal_finance.tools.overview import get_financial_overview
    result = get_financial_overview("2026-04")

    # Required structure for the client to render.
    assert set(result.keys()) >= {
        "period", "start", "end", "headline",
        "top_categories", "top_merchants", "recent_transactions", "accounts",
    }
    assert len(result["top_categories"]) > 0
    assert len(result["top_merchants"]) > 0
    # 4 banks × 1 account_type each.
    assert len(result["accounts"]) == 4


def test_overview_top_categories_excludes_payments(multi_bank_db):
    from personal_finance.tools.overview import get_financial_overview
    result = get_financial_overview("2026-04")

    cats = {c["category"] for c in result["top_categories"]}
    assert "Payments & Credits" not in cats
    assert "Transfers" not in cats


def test_overview_account_block_is_per_institution_account_type(multi_bank_db):
    from personal_finance.tools.overview import get_financial_overview
    result = get_financial_overview("2026-04")

    institutions = {a["institution"] for a in result["accounts"]}
    assert institutions == {"chase", "amex", "discover", "wells_fargo"}

    chase = next(a for a in result["accounts"] if a["institution"] == "chase")
    # Chase fixture has 8 rows; debits (charges) + credits (the $500 payment).
    assert chase["txn_count"] == 8
    assert chase["debits"] > 0
    assert chase["credits"] == 500.0


def test_overview_recent_transactions_sorted_desc(multi_bank_db):
    from personal_finance.tools.overview import get_financial_overview
    result = get_financial_overview("2026-04")

    dates = [t["date"] for t in result["recent_transactions"]]
    assert dates == sorted(dates, reverse=True)
    assert len(dates) <= 10


def test_overview_top_n_clamped(multi_bank_db):
    from personal_finance.tools.overview import get_financial_overview
    result = get_financial_overview("2026-04", top_n=999)
    # Even with a huge top_n, can't return more categories than exist.
    assert len(result["top_categories"]) <= 25


def test_overview_with_quarterly_period(multi_bank_db):
    from personal_finance.tools.overview import get_financial_overview
    result = get_financial_overview("2026-Q2")
    assert result["start"] == "2026-04-01"
    assert result["end"] == "2026-06-30"


def test_overview_empty_db_returns_zeros(tmp_path, monkeypatch):
    from personal_finance.tools.overview import get_financial_overview

    db_file = tmp_path / "empty.duckdb"
    connect(db_file).close()  # schema only

    monkeypatch.setattr(
        "personal_finance.tools.overview.get_db", lambda: connect(db_file)
    )

    result = get_financial_overview()
    assert result["headline"]["total_expense"] == 0
    assert result["headline"]["transaction_count"] == 0
    assert result["top_categories"] == []
    assert result["accounts"] == []
