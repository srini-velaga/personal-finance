"""Parse a CSV file into normalized ``Transaction`` rows using a ``Profile``.

This is the only module that touches raw CSVs. Errors are raised; the
pipeline above decides whether to skip the file or surface the failure.
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from personal_finance.ingest.fingerprint import clean_description, txn_fingerprint
from personal_finance.ingest.profile import Profile
from personal_finance.models import Transaction


class CsvParseError(ValueError):
    """Raised when a row can't be parsed under the given profile."""


def _parse_amount(raw: str, sign_convention: str) -> Decimal:
    """Convert a raw amount cell to the unified sign convention.

    Unified convention: **positive = expense, negative = income**.

    ``sign_convention`` describes the *source* CSV:
      * ``negative_is_expense`` — source has negative for charges (Chase).
        We flip the sign.
      * ``positive_is_expense`` — source has positive for charges (Discover).
        Pass-through.
    """
    cleaned = raw.strip().replace("$", "").replace(",", "")
    if not cleaned:
        raise CsvParseError("empty amount cell")
    try:
        value = Decimal(cleaned)
    except InvalidOperation as e:
        raise CsvParseError(f"could not parse amount: {raw!r}") from e

    if sign_convention == "negative_is_expense":
        return -value
    if sign_convention == "positive_is_expense":
        return value
    raise CsvParseError(f"unknown amount_sign: {sign_convention!r}")


def _parse_date(raw: str, fmt: str) -> date:
    return datetime.strptime(raw.strip(), fmt).date()


def parse_csv(path: str | Path, profile: Profile) -> list[Transaction]:
    """Parse ``path`` into ``Transaction`` objects using ``profile``.

    Each row must contain non-empty cells for the columns the profile maps to
    ``transaction_date``, ``description``, and ``amount``. Other columns are
    optional. Rows that fail validation are skipped silently in v1 (and will
    be surfaced as warnings once we add structured logging).
    """
    path = Path(path)
    cols = profile.columns
    transactions: list[Transaction] = []

    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                txn_date = _parse_date(row[cols["transaction_date"]], profile.date_format)
                description = row[cols["description"]].strip()
                if not description:
                    continue
                amount = _parse_amount(row[cols["amount"]], profile.amount_sign)
            except (KeyError, CsvParseError):
                continue

            post_date: date | None = None
            if "post_date" in cols and row.get(cols["post_date"], "").strip():
                try:
                    post_date = _parse_date(row[cols["post_date"]], profile.date_format)
                except CsvParseError:
                    post_date = None

            original_category: str | None = None
            if "category" in cols:
                cat = row.get(cols["category"], "").strip()
                original_category = cat or None

            description_clean = clean_description(description)
            fingerprint = txn_fingerprint(
                txn_date.isoformat(),
                amount,
                description_clean,
                profile.institution,
                profile.account_type,
            )

            transactions.append(
                Transaction(
                    txn_fingerprint=fingerprint,
                    institution=profile.institution,
                    account_type=profile.account_type,
                    transaction_date=txn_date,
                    post_date=post_date,
                    description=description,
                    description_clean=description_clean,
                    amount=amount,
                    original_category=original_category,
                    source_file=str(path),
                )
            )

    return transactions
