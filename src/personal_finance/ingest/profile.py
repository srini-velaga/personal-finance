"""Bank statement profiles — declarative descriptions of CSV formats.

A profile is a JSON file with this shape::

    {
      "institution": "chase",
      "account_type": "credit_card",
      "header_fingerprint": ["Transaction Date", "Post Date", ...],
      "columns": {
        "transaction_date": "Transaction Date",
        "post_date": "Post Date",
        "description": "Description",
        "amount": "Amount",
        "category": "Category"
      },
      "amount_sign": "negative_is_expense",  // or "positive_is_expense"
      "date_format": "%m/%d/%Y"
    }

Profiles are matched to incoming CSVs by checking that the file's header row
is a *superset* of the profile's ``header_fingerprint``. This lets a profile
work even if the bank adds an extra column.

Two profile sources are merged at load time:
  * shipped: ``src/personal_finance/profiles/*.json`` (bundled with the package)
  * user-added: ``{data_dir}/profiles/*.json``  (auto-generated or hand-edited)

User profiles take precedence on name collision.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from personal_finance.config import user_profiles_dir

# Profiles shipped inside the package — sibling of this module's parent.
_PACKAGE_PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"

AmountSign = Literal["negative_is_expense", "positive_is_expense"]


@dataclass(frozen=True)
class Profile:
    institution: str
    account_type: str
    header_fingerprint: tuple[str, ...]
    columns: dict[str, str]
    amount_sign: AmountSign
    date_format: str

    @property
    def name(self) -> str:
        """Stable identifier: ``{institution}_{account_type}``."""
        return f"{self.institution}_{self.account_type}"

    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        return cls(
            institution=data["institution"],
            account_type=data["account_type"],
            header_fingerprint=tuple(data["header_fingerprint"]),
            columns=dict(data["columns"]),
            amount_sign=data["amount_sign"],
            date_format=data["date_format"],
        )


def _load_dir(dir_path: Path) -> dict[str, Profile]:
    profiles: dict[str, Profile] = {}
    if not dir_path.exists():
        return profiles
    for json_file in sorted(dir_path.glob("*.json")):
        with json_file.open() as f:
            data = json.load(f)
        prof = Profile.from_dict(data)
        profiles[prof.name] = prof
    return profiles


def load_profiles() -> list[Profile]:
    """Load all profiles: shipped first, then user dir (user overrides shipped)."""
    merged = _load_dir(_PACKAGE_PROFILES_DIR)
    merged.update(_load_dir(user_profiles_dir()))
    return list(merged.values())


def match_profile(headers: list[str], profiles: list[Profile]) -> Profile | None:
    """Return the first profile whose ``header_fingerprint`` is a subset of ``headers``.

    The match is order-independent and case-sensitive. Whitespace in headers
    is stripped before comparison.
    """
    header_set = {h.strip() for h in headers}
    for prof in profiles:
        if set(prof.header_fingerprint).issubset(header_set):
            return prof
    return None
