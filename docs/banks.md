# Bank profile reference

One row per shipped profile. Useful as a memory aid when adding new banks or debugging an unexpected ingest.

For the schema and how to add a new profile, see [AGENTS.md](../AGENTS.md#how-to-add-a-new-bank-profile).

## Shipped profiles

| Profile | Format | Sign convention | Date format | Notes |
|---|---|---|---|---|
| [`chase_credit`](../src/personal_finance/profiles/chase_credit.json) | CSV | `negative_is_expense` (charges are negative) | `MM/DD/YYYY` | Type column distinguishes Sale / Payment / Refund / Fee / Reversal. Filename may be `.CSV` (uppercase). |
| [`amex_credit`](../src/personal_finance/profiles/amex_credit.json) | CSV | `positive_is_expense` | `MM/DD/YYYY` | Multi-line `Extended Details` field (newlines inside quoted cells). Categories use Parent-Sub format with hyphen, e.g. `Merchandise & Supplies-Groceries`. |
| [`discover_credit`](../src/personal_finance/profiles/discover_credit.json) | CSV | `positive_is_expense` | `MM/DD/YYYY` | UTF-8 BOM on header row. Amounts can contain embedded commas (`-1,746.98`). |
| [`wells_fargo_credit`](../src/personal_finance/profiles/wells_fargo_credit.json) | CSV | `positive_is_expense` | `MM/DD/YYYY` | `$`-prefixed amounts (`$10.37`); refunds/payments use `-$` prefix. Has both `Master Category` (used) and `Subcategory` (preserved in `original_category` indirectly). Trailing empty column in header. |

## Tested fixtures

Anonymized samples live in [`tests/fixtures/`](../tests/fixtures/). Each preserves the format quirks of the real bank export — fake merchants and amounts, real encoding/whitespace/multi-line behavior.

- `tests/fixtures/chase_credit_sample.csv` (8 rows)
- `tests/fixtures/amex_credit_sample.csv` (5 rows; one multi-line Extended Details)
- `tests/fixtures/discover_credit_sample.csv` (6 rows; BOM + comma amount)
- `tests/fixtures/wells_fargo_credit_sample.csv` (6 rows; `$`-prefix + `-$` refund)

## Real-data smoke (v0.4 / v0.5)

Ingested 504 transactions across 4 banks (Chase, Amex, Discover, Wells Fargo) from `~/Documents/personal/financial-statements/statements/` into a throwaway DuckDB. No file uncategorized at the profile level; ~1.6% (8 transactions) landed in `Uncategorized` at the category level — all international or local-merchant transactions Wells Fargo itself had tagged "Miscellaneous".

Distribution: Groceries 94 · Food & Dining 91 · Shopping 86 · Transportation 75 · Payments & Credits 63 · Bills & Utilities 39 · Fees 15 · Travel 14 · Entertainment 14 · Health 3 · Transfers 1 · Home 1 · Uncategorized 8.

## Known gaps

- **Chase checking** — the `Chase0281...CSV` in the test folder has Chase's *credit* CSV format (Type column with Sale/Payment), not checking. Chase checking uses a Details column (DEBIT/CREDIT) and needs its own profile + fixture. Not shipped yet.
- **PDF-only banks** — BofA exports PDFs only. The PDFs in the statements folder (BofA, Chase, Wells Fargo) are all currently skipped because no PDF parser is wired up. PDF ingest is the next major milestone.
