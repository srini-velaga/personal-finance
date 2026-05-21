"""Tests for the unified category mapping layer."""

from __future__ import annotations

import shutil
from decimal import Decimal
from pathlib import Path

import pytest

from personal_finance.categories import UNIFIED_CATEGORIES, categorize, load_mappings
from personal_finance.db import connect
from personal_finance.ingest import ingest_folder, load_profiles
from personal_finance.models import Transaction

FIXTURE = Path(__file__).parent / "fixtures" / "chase_credit_sample.csv"


def _txn(
    *,
    institution: str = "chase",
    account_type: str = "credit_card",
    description: str,
    amount: str,
    original_category: str | None = None,
) -> Transaction:
    return Transaction(
        txn_fingerprint="fp-" + description,
        institution=institution,
        account_type=account_type,
        transaction_date="2026-04-01",
        description=description,
        description_clean=description.upper(),
        amount=Decimal(amount),
        original_category=original_category,
        source_file="test",
    )


@pytest.fixture(autouse=True)
def _reset_cache():
    load_mappings.cache_clear()
    yield
    load_mappings.cache_clear()


def test_institution_mapping_wins(_reset_cache=None):
    # Chase "Food & Drink" → unified "Food & Dining".
    t = _txn(description="STARBUCKS STORE 12345", amount="5.75",
             original_category="Food & Drink")
    assert categorize(t) == "Food & Dining"


def test_keyword_fallback_when_no_institution_category():
    t = _txn(description="WHOLE FOODS MARKET", amount="83.42")
    assert categorize(t) == "Groceries"


def test_keyword_fallback_when_institution_unmapped():
    # Chase doesn't have a "Mystery" category mapping; keyword wins.
    t = _txn(description="NETFLIX.COM", amount="15.49",
             original_category="Mystery")
    assert categorize(t) == "Entertainment"


def test_unknown_falls_back_to_uncategorized():
    t = _txn(description="SOMETHING NOBODY HAS EVER HEARD OF", amount="10.00")
    assert categorize(t) == "Uncategorized"


def test_negative_credit_card_amount_is_payment():
    t = _txn(description="PAYMENT THANK YOU - WEB", amount="-500.00")
    assert categorize(t) == "Payments & Credits"


def test_negative_checking_amount_is_income():
    t = _txn(
        institution="chase",
        account_type="checking",
        description="EMPLOYER DIRECT DEPOSIT",
        amount="-3500.00",
    )
    assert categorize(t) == "Income"


def test_all_mapped_categories_are_in_unified_set():
    mappings = load_mappings()
    for _bank, mapping in mappings["institution_mappings"].items():
        for unified in mapping.values():
            assert unified in UNIFIED_CATEGORIES, f"{unified!r} not in taxonomy"
    for rule in mappings["keyword_rules"]:
        assert rule["category"] in UNIFIED_CATEGORIES, rule


def test_ingest_populates_unified_category(tmp_path):
    folder = tmp_path / "statements"
    folder.mkdir()
    shutil.copy(FIXTURE, folder / "chase_april.csv")

    conn = connect(tmp_path / "test.duckdb")
    try:
        ingest_folder(folder, conn, profiles=load_profiles())
        rows = conn.execute(
            "SELECT description, unified_category, amount FROM transactions ORDER BY transaction_date"
        ).fetchall()
    finally:
        conn.close()

    by_desc = {desc.upper(): (cat, float(amt)) for desc, cat, amt in rows}

    # Spot-check the mapping on each fixture row.
    assert by_desc["STARBUCKS STORE 12345"][0] == "Food & Dining"
    assert by_desc["WHOLE FOODS MARKET"][0] == "Groceries"
    assert by_desc["UBER TRIP"][0] == "Travel"  # Chase tags Uber as Travel
    assert by_desc["AMAZON.COM*123ABC"][0] == "Shopping"
    assert by_desc["PAYMENT THANK YOU - WEB"][0] == "Payments & Credits"
    assert by_desc["SHELL OIL 9876543"][0] == "Transportation"
    assert by_desc["NETFLIX.COM"][0] == "Bills & Utilities"  # Chase classifies as Bills
    assert by_desc["TRADER JOE'S #555"][0] == "Groceries"


def test_recategorize_all_tool(tmp_path, monkeypatch):
    """Ingest, deliberately corrupt one row's category, then recategorize and assert it's restored."""
    db_file = tmp_path / "test.duckdb"
    folder = tmp_path / "statements"
    folder.mkdir()
    shutil.copy(FIXTURE, folder / "chase_april.csv")

    conn = connect(db_file)
    ingest_folder(folder, conn, profiles=load_profiles())
    conn.execute(
        "UPDATE transactions SET unified_category = 'WRONG' WHERE description LIKE '%STARBUCKS%'"
    )
    wrong_count = conn.execute(
        "SELECT COUNT(*) FROM transactions WHERE unified_category = 'WRONG'"
    ).fetchone()[0]
    assert wrong_count == 1
    conn.close()

    def _get_db():
        return connect(db_file)

    monkeypatch.setattr("personal_finance.tools.categories.get_db", _get_db)

    from personal_finance.tools.categories import recategorize_all
    result = recategorize_all()

    assert result["inspected"] == 8
    assert result["updated"] == 1
    # Histogram covers all 8 rows.
    total = sum(item["count"] for item in result["histogram"])
    assert total == 8

    conn = connect(db_file)
    final = conn.execute(
        "SELECT unified_category FROM transactions WHERE description LIKE '%STARBUCKS%'"
    ).fetchone()
    conn.close()
    assert final[0] == "Food & Dining"
