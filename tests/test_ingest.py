"""End-to-end ingest tests using the bundled Chase profile + a sample CSV."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from personal_finance.db import connect
from personal_finance.ingest import ingest_folder, load_profiles, match_profile
from personal_finance.ingest.csv_parser import parse_csv
from personal_finance.ingest.fingerprint import clean_description, txn_fingerprint

FIXTURE = Path(__file__).parent / "fixtures" / "chase_credit_sample.csv"


@pytest.fixture
def profiles():
    return load_profiles()


@pytest.fixture
def conn(tmp_path):
    db_file = tmp_path / "test.duckdb"
    c = connect(db_file)
    yield c
    c.close()


@pytest.fixture
def statement_dir(tmp_path):
    """Copy the fixture into a tmp dir so ingest works on a real path."""
    folder = tmp_path / "statements"
    folder.mkdir()
    shutil.copy(FIXTURE, folder / "chase_april.csv")
    return folder


def test_chase_profile_loaded(profiles):
    names = {p.name for p in profiles}
    assert "chase_credit_card" in names


def test_profile_matches_chase_headers(profiles):
    headers = [
        "Transaction Date", "Post Date", "Description",
        "Category", "Type", "Amount", "Memo",
    ]
    p = match_profile(headers, profiles)
    assert p is not None
    assert p.institution == "chase"
    assert p.account_type == "credit_card"


def test_profile_does_not_match_random_headers(profiles):
    assert match_profile(["foo", "bar", "baz"], profiles) is None


def test_parse_csv_normalizes_signs_and_categories(profiles):
    profile = match_profile(
        ["Transaction Date", "Post Date", "Description", "Category", "Type", "Amount", "Memo"],
        profiles,
    )
    assert profile is not None
    txns = parse_csv(FIXTURE, profile)

    # 8 rows in the fixture, none should be dropped.
    assert len(txns) == 8

    # Chase has negative=charge; unified convention is positive=expense.
    # The Starbucks row (-5.75 in source) should become +5.75.
    starbucks = next(t for t in txns if "STARBUCKS" in t.description.upper())
    assert starbucks.amount == 5.75

    # The payment row (500.00 in source) is income → should be negative.
    payment = next(t for t in txns if "PAYMENT" in t.description.upper())
    assert payment.amount == -500.00

    # Original category passed through.
    assert starbucks.original_category == "Food & Drink"


def test_fingerprint_is_stable():
    fp1 = txn_fingerprint("2026-04-02", __import__("decimal").Decimal("5.75"),
                          clean_description("Starbucks Store 12345"),
                          "chase", "credit_card")
    fp2 = txn_fingerprint("2026-04-02", __import__("decimal").Decimal("5.75"),
                          clean_description("starbucks store 12345"),
                          "chase", "credit_card")
    assert fp1 == fp2, "description casing should not affect fingerprint"


def test_ingest_folder_inserts_all(conn, statement_dir, profiles):
    result = ingest_folder(statement_dir, conn, profiles=profiles)
    assert result.files_scanned == 1
    assert result.files_ingested == 1
    assert result.transactions_inserted == 8

    count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    assert count == 8


def test_ingest_is_idempotent_on_same_file(conn, statement_dir, profiles):
    # First run
    r1 = ingest_folder(statement_dir, conn, profiles=profiles)
    assert r1.transactions_inserted == 8

    # Second run — file hash already in processing_log
    r2 = ingest_folder(statement_dir, conn, profiles=profiles)
    assert r2.files_skipped_already_processed == 1
    assert r2.transactions_inserted == 0

    count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    assert count == 8


def test_ingest_dedupes_across_files(conn, statement_dir, tmp_path, profiles):
    # First file
    r1 = ingest_folder(statement_dir, conn, profiles=profiles)
    assert r1.transactions_inserted == 8

    # Different filename, identical contents → file hash matches → skipped.
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    shutil.copy(FIXTURE, other_dir / "chase_april_renamed.csv")
    r2 = ingest_folder(other_dir, conn, profiles=profiles)
    assert r2.files_skipped_already_processed == 1
    assert r2.transactions_inserted == 0


def test_ingest_skips_unknown_format(conn, tmp_path, profiles):
    folder = tmp_path / "unknown"
    folder.mkdir()
    (folder / "mystery.csv").write_text("foo,bar,baz\n1,2,3\n")
    result = ingest_folder(folder, conn, profiles=profiles)
    assert result.files_scanned == 1
    assert result.files_skipped_no_profile == 1
    assert result.transactions_inserted == 0
