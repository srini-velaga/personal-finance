"""Pydantic models used at the ingest boundary.

These validate parsed CSV rows before they hit DuckDB. We don't model DB
rows back into Python — DuckDB returns plain tuples/dicts that we hand to
the agent.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class Transaction(BaseModel):
    """A normalized transaction, ready for insertion.

    Sign convention: ``amount`` is **positive for expenses/debits** and
    **negative for income/credits**, regardless of how the source bank
    represents it. Profiles handle the per-bank conversion.
    """

    txn_fingerprint: str
    institution: str
    account_type: str  # "credit_card" | "checking" | "savings"
    transaction_date: date
    post_date: date | None = None
    description: str
    description_clean: str
    amount: Decimal
    original_category: str | None = None
    unified_category: str | None = None
    source_file: str
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
