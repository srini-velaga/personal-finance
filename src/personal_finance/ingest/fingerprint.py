"""Hash helpers for file-level and transaction-level deduplication.

Two layers:
  1. ``file_hash`` — SHA-256 of file bytes. Used to skip re-ingesting an
     unchanged file.
  2. ``txn_fingerprint`` — SHA-256 of (date, amount, cleaned description,
     institution, account_type). Used as the transactions PK so the same
     real-world transaction can't appear twice even if it's in two files.
"""

from __future__ import annotations

import hashlib
import re
from decimal import Decimal
from pathlib import Path

_WHITESPACE = re.compile(r"\s+")


def clean_description(raw: str) -> str:
    """Normalize a description for fingerprinting: uppercase, collapse whitespace.

    We deliberately do *not* strip merchant suffixes (store numbers, cities)
    here — those are legitimate signal and removing them would over-collapse.
    """
    return _WHITESPACE.sub(" ", raw.upper()).strip()


def txn_fingerprint(
    transaction_date: str,
    amount: Decimal,
    description_clean: str,
    institution: str,
    account_type: str,
) -> str:
    """Compute the stable per-transaction hash.

    ``transaction_date`` is the ISO date string (YYYY-MM-DD). ``amount`` is
    quantized to 2 decimals so that ``Decimal('5.00')`` and ``Decimal('5.0')``
    fingerprint identically.
    """
    amount_str = f"{amount.quantize(Decimal('0.01')):.2f}"
    key = f"{transaction_date}|{amount_str}|{description_clean}|{institution}|{account_type}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def file_hash(path: str | Path, *, chunk_size: int = 65536) -> str:
    """Return the SHA-256 of a file's contents (hex)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()
