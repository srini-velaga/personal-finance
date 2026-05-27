"""Tests for the period parser — covers calendar, rolling, and DB-relative patterns."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from personal_finance.db import connect
from personal_finance.tools.spending import _parse_period


# ---------- calendar patterns (existing behavior, keep covered) ----------

def test_parse_month():
    start, end = _parse_period("2026-04")
    assert start == date(2026, 4, 1)
    assert end == date(2026, 4, 30)


def test_parse_month_december_edge():
    start, end = _parse_period("2026-12")
    assert end == date(2026, 12, 31)


def test_parse_quarter():
    start, end = _parse_period("2026-Q2")
    assert start == date(2026, 4, 1)
    assert end == date(2026, 6, 30)


def test_parse_quarter_q4_ends_dec_31():
    start, end = _parse_period("2026-Q4")
    assert start == date(2026, 10, 1)
    assert end == date(2026, 12, 31)


def test_parse_quarter_invalid():
    with pytest.raises(ValueError, match="invalid quarter"):
        _parse_period("2026-Q5")


def test_parse_year():
    start, end = _parse_period("2025")
    assert start == date(2025, 1, 1)
    assert end == date(2025, 12, 31)


def test_parse_iso_date():
    start, end = _parse_period("2026-04-15")
    assert start == end == date(2026, 4, 15)


def test_parse_unrecognized_raises():
    with pytest.raises(ValueError, match="unrecognized period"):
        _parse_period("not-a-period")


# ---------- case insensitivity ----------

def test_case_insensitive():
    s1, e1 = _parse_period("2026-q2")
    s2, e2 = _parse_period("2026-Q2")
    assert (s1, e1) == (s2, e2)

    s3, e3 = _parse_period("YTD")
    s4, e4 = _parse_period("ytd")
    assert (s3, e3) == (s4, e4)


# ---------- rolling / relative patterns ----------

def test_parse_ytd():
    start, end = _parse_period("ytd")
    today = date.today()
    assert start == date(today.year, 1, 1)
    assert end == today


def test_parse_last_30_days():
    start, end = _parse_period("last_30_days")
    today = date.today()
    assert end == today
    assert (end - start).days == 29  # inclusive 30-day window


def test_parse_last_90_days():
    start, end = _parse_period("last_90_days")
    today = date.today()
    assert end == today
    assert (end - start).days == 89


def test_parse_last_12_months():
    start, end = _parse_period("last_12_months")
    today = date.today()
    assert end == today
    assert (end - start).days == 365


# ---------- DB-relative ----------

def test_parse_all_requires_conn():
    with pytest.raises(ValueError, match="needs a DB connection"):
        _parse_period("all")


def test_parse_lifetime_requires_conn():
    with pytest.raises(ValueError, match="needs a DB connection"):
        _parse_period("lifetime")


def test_parse_all_uses_db_min_max(tmp_path):
    conn = connect(tmp_path / "test.duckdb")
    try:
        # Insert two transactions far apart in time.
        for d, fp in [
            (date(2023, 1, 15), "fp-old"),
            (date(2025, 11, 30), "fp-mid"),
            (date(2026, 4, 1), "fp-new"),
        ]:
            conn.execute(
                """
                INSERT INTO transactions (
                    txn_fingerprint, institution, account_type,
                    transaction_date, description, description_clean,
                    amount, source_file, ingested_at
                ) VALUES (?, 'test', 'credit_card', ?, 'X', 'X', 1.00, 't', '2026-05-01')
                """,
                [fp, d],
            )

        start, end = _parse_period("all", conn=conn)
        assert start == date(2023, 1, 15)
        assert end == date(2026, 4, 1)
    finally:
        conn.close()


def test_parse_all_on_empty_db_returns_today_today(tmp_path):
    conn = connect(tmp_path / "empty.duckdb")
    try:
        start, end = _parse_period("all", conn=conn)
        assert start == end == date.today()
    finally:
        conn.close()
