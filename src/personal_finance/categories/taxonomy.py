"""The unified category taxonomy.

Per spec §4.2: start small, extend organically as real data exposes gaps.
The canonical list lives here as a frozenset; mappings/keyword rules live
in ``mappings.json`` next door so non-coders can edit them.

When you add a new category here, also add it to the institution mapping
and/or keyword rules in ``mappings.json``.
"""

from __future__ import annotations

UNIFIED_CATEGORIES: frozenset[str] = frozenset(
    {
        "Food & Dining",
        "Groceries",
        "Transportation",
        "Travel",
        "Shopping",
        "Bills & Utilities",
        "Entertainment",
        "Health",
        "Home",
        "Income",
        "Transfers",
        "Payments & Credits",
        "Fees",
        "Uncategorized",
    }
)

UNCATEGORIZED = "Uncategorized"
