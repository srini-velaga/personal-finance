"""Map a parsed transaction to a unified category.

Precedence (first match wins):
  1. Sign-based: negative amount on a credit card → ``Payments & Credits``;
     negative amount on checking/savings → ``Income``.
  2. Institution mapping: the bank's own category (e.g. Chase "Food & Drink")
     mapped to a unified label.
  3. Keyword rule: regex over the cleaned description.
  4. Fallback: ``Uncategorized``.

Mappings live in ``mappings.json`` next to this module; user overrides go in
``{data_dir}/categories.json`` and shadow the shipped file when present.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

from personal_finance.categories.taxonomy import UNCATEGORIZED, UNIFIED_CATEGORIES
from personal_finance.config import data_dir
from personal_finance.models import Transaction

_PACKAGE_MAPPINGS = Path(__file__).resolve().parent / "mappings.json"


def _user_mappings_path() -> Path:
    return data_dir() / "categories.json"


@lru_cache(maxsize=1)
def load_mappings() -> dict[str, Any]:
    """Load mappings: shipped file, optionally overridden by the user's copy.

    The user's file is a complete replacement when present (not a merge) — it
    keeps the override model simple. Users who only want to add a few rules
    can copy the shipped file and edit it.
    """
    path = _user_mappings_path() if _user_mappings_path().exists() else _PACKAGE_MAPPINGS
    with path.open() as f:
        data = json.load(f)
    # Pre-compile keyword regexes for speed.
    for rule in data.get("keyword_rules", []):
        rule["_re"] = re.compile(rule["pattern"], re.IGNORECASE)
    return data


def _refresh_for_tests() -> None:
    """Test hook — call after monkeypatching paths to clear the cached mapping."""
    load_mappings.cache_clear()


def categorize(txn: Transaction) -> str:
    """Return the unified category for a transaction."""
    mappings = load_mappings()

    # 1. Sign-based shortcut for income/payments.
    if txn.amount < Decimal("0"):
        if txn.account_type == "credit_card":
            return "Payments & Credits"
        return "Income"

    # 2. Institution category mapping.
    if txn.original_category:
        inst_map = mappings.get("institution_mappings", {}).get(txn.institution, {})
        mapped = inst_map.get(txn.original_category)
        if mapped and mapped in UNIFIED_CATEGORIES:
            return mapped

    # 3. Keyword fallback.
    description = txn.description_clean
    for rule in mappings.get("keyword_rules", []):
        if rule["_re"].search(description):
            cat = rule["category"]
            if cat in UNIFIED_CATEGORIES:
                return cat

    return UNCATEGORIZED
