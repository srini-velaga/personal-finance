"""Tests for the Amex, Discover, and Wells Fargo CSV profiles.

Each bank has a distinct quirk we want to lock down:
  * Amex: multi-line ``Extended Details`` field (quoted with newlines).
  * Discover: UTF-8 BOM in the header, commas embedded in amounts.
  * Wells Fargo: ``$``-prefixed amounts plus ``-$`` for refunds/payments.
"""

from __future__ import annotations

import shutil
from decimal import Decimal
from pathlib import Path

import pytest

from personal_finance.db import connect
from personal_finance.ingest import ingest_folder, load_profiles, match_profile
from personal_finance.ingest.csv_parser import _parse_amount, parse_csv

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def profiles():
    return load_profiles()


# ---------- header matching ----------

def test_amex_profile_matches(profiles):
    headers = [
        "Date", "Description", "Amount", "Extended Details",
        "Appears On Your Statement As", "Address", "City/State",
        "Zip Code", "Country", "Reference", "Category",
    ]
    p = match_profile(headers, profiles)
    assert p is not None and p.name == "amex_credit_card"


def test_discover_profile_matches(profiles):
    # Headers as DictReader would see them (BOM stripped via utf-8-sig).
    headers = ["Trans. Date", "Description", "Amount", "Category"]
    p = match_profile(headers, profiles)
    assert p is not None and p.name == "discover_credit_card"


def test_wells_fargo_profile_matches(profiles):
    headers = [
        "Master Category", "Subcategory", "Date", "Location", "Payee",
        "Description", "Payment Method", "Amount", "",
    ]
    p = match_profile(headers, profiles)
    assert p is not None and p.name == "wells_fargo_credit_card"


# ---------- amount parsing edge cases ----------

def test_parse_amount_strips_dollar_and_commas():
    # Wells Fargo charge: $10.37 positive expense.
    assert _parse_amount("$10.37", "positive_is_expense") == Decimal("10.37")
    # Wells Fargo refund: -$136.74 income.
    assert _parse_amount("-$136.74", "positive_is_expense") == Decimal("-136.74")
    # Discover payment: -1,746.98 with embedded comma.
    assert _parse_amount("-1,746.98", "positive_is_expense") == Decimal("-1746.98")


# ---------- end-to-end parse with each profile ----------

def test_amex_fixture_parses_and_categorizes(profiles):
    profile = next(p for p in profiles if p.name == "amex_credit_card")
    txns = parse_csv(FIXTURES / "amex_credit_sample.csv", profile)

    assert len(txns) == 5

    by_desc = {t.description: t for t in txns}

    # Charges keep their sign (positive_is_expense, pass-through).
    grocery = by_desc["SHOPRITE GROCERY 0042"]
    assert grocery.amount == Decimal("87.55")
    assert grocery.original_category == "Merchandise & Supplies-Groceries"

    # Multi-line Extended Details didn't break row parsing.
    fuel = by_desc["SHELL OIL 9876"]
    assert fuel.amount == Decimal("42.18")

    # Payment is negative.
    payment = by_desc["AUTOPAY PAYMENT - THANK YOU"]
    assert payment.amount == Decimal("-1250.00")


def test_discover_fixture_parses_and_categorizes(profiles):
    profile = next(p for p in profiles if p.name == "discover_credit_card")
    txns = parse_csv(FIXTURES / "discover_credit_sample.csv", profile)

    assert len(txns) == 6

    by_desc = {t.description: t for t in txns}

    # Embedded comma in amount.
    payment = by_desc["DIRECTPAY FULL BALANCE"]
    assert payment.amount == Decimal("-1425.50")

    # Original Discover categories preserved.
    grocery = by_desc["WEGMANS FOOD MARKETS 0123"]
    assert grocery.original_category == "Supermarkets"


def test_wells_fargo_fixture_parses(profiles):
    profile = next(p for p in profiles if p.name == "wells_fargo_credit_card")
    txns = parse_csv(FIXTURES / "wells_fargo_credit_sample.csv", profile)

    assert len(txns) == 6

    by_desc = {t.description: t for t in txns}

    # $-prefixed positive amount.
    gas = by_desc["WAWA 1234 EXTON        ,PA"]
    assert gas.amount == Decimal("32.18")
    assert gas.original_category == "Auto/Transportation"

    # -$-prefixed negative amount (payment).
    payment = by_desc["ONLINE PAYMENT THANK YOU"]
    assert payment.amount == Decimal("-1450.00")


# ---------- ingest-level integration: unified category mapping ----------

def test_amex_ingest_maps_to_unified_categories(tmp_path, profiles):
    folder = tmp_path / "stmt"
    folder.mkdir()
    shutil.copy(FIXTURES / "amex_credit_sample.csv", folder / "amex.csv")

    conn = connect(tmp_path / "test.duckdb")
    try:
        result = ingest_folder(folder, conn, profiles=profiles)
        assert result.transactions_inserted == 5

        rows = conn.execute(
            "SELECT description, unified_category FROM transactions"
        ).fetchall()
    finally:
        conn.close()

    mapping = {desc: cat for desc, cat in rows}
    assert mapping["SHOPRITE GROCERY 0042"] == "Groceries"
    assert mapping["SHELL OIL 9876"] == "Transportation"
    assert mapping["COMCAST CABLE INTERNET"] == "Bills & Utilities"
    assert mapping["AMAZON.COM*MK1234ABC"] == "Shopping"
    assert mapping["AUTOPAY PAYMENT - THANK YOU"] == "Payments & Credits"


def test_discover_ingest_maps_to_unified_categories(tmp_path, profiles):
    folder = tmp_path / "stmt"
    folder.mkdir()
    shutil.copy(FIXTURES / "discover_credit_sample.csv", folder / "discover.csv")

    conn = connect(tmp_path / "test.duckdb")
    try:
        result = ingest_folder(folder, conn, profiles=profiles)
        assert result.transactions_inserted == 6

        rows = conn.execute(
            "SELECT description, unified_category FROM transactions"
        ).fetchall()
    finally:
        conn.close()

    mapping = {desc: cat for desc, cat in rows}
    assert mapping["WEGMANS FOOD MARKETS 0123"] == "Groceries"
    assert mapping["CHICK-FIL-A #1234 EXTON PA"] == "Food & Dining"
    assert mapping["EXXONMOBIL EXTON PA"] == "Transportation"
    assert mapping["DIRECTPAY FULL BALANCE"] == "Payments & Credits"


def test_wells_fargo_ingest_maps_to_unified_categories(tmp_path, profiles):
    folder = tmp_path / "stmt"
    folder.mkdir()
    shutil.copy(FIXTURES / "wells_fargo_credit_sample.csv", folder / "wf.csv")

    conn = connect(tmp_path / "test.duckdb")
    try:
        result = ingest_folder(folder, conn, profiles=profiles)
        assert result.transactions_inserted == 6

        rows = conn.execute(
            "SELECT description, unified_category FROM transactions"
        ).fetchall()
    finally:
        conn.close()

    mapping = {desc: cat for desc, cat in rows}
    # Auto/Transportation → Transportation
    assert mapping["WAWA 1234 EXTON        ,PA"] == "Transportation"
    # Food/Drink → Food & Dining
    assert mapping["CHIPOTLE 9876 EXTON        ,PA"] == "Food & Dining"
    # Bills/Utilities → Bills & Utilities
    assert mapping["NETFLIX.COM LOS GATOS    ,CA"] == "Bills & Utilities"
    # Negative amount → Payments & Credits (sign shortcut wins)
    assert mapping["ONLINE PAYMENT THANK YOU"] == "Payments & Credits"


def test_all_four_banks_coexist_in_one_ingest(tmp_path, profiles):
    """Drop one CSV from each bank in the same folder; profile matching should still work."""
    folder = tmp_path / "stmt"
    folder.mkdir()
    shutil.copy(FIXTURES / "chase_credit_sample.csv", folder / "chase.csv")
    shutil.copy(FIXTURES / "amex_credit_sample.csv", folder / "amex.csv")
    shutil.copy(FIXTURES / "discover_credit_sample.csv", folder / "discover.csv")
    shutil.copy(FIXTURES / "wells_fargo_credit_sample.csv", folder / "wf.csv")

    conn = connect(tmp_path / "test.duckdb")
    try:
        result = ingest_folder(folder, conn, profiles=profiles)
        assert result.files_scanned == 4
        assert result.files_ingested == 4
        # 8 (chase) + 5 (amex) + 6 (discover) + 6 (wf) = 25
        assert result.transactions_inserted == 25

        institutions = conn.execute(
            "SELECT DISTINCT institution FROM transactions ORDER BY institution"
        ).fetchall()
    finally:
        conn.close()

    assert [r[0] for r in institutions] == ["amex", "chase", "discover", "wells_fargo"]
