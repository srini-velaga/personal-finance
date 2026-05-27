# AGENTS.md

Guidance for AI coding agents (Claude Code, Cursor, Codex, etc.) working in this repo. Follows the [agents.md](https://agents.md/) convention.

## What this project is

A self-hosted **MCP server** that gives an AI agent personal financial analysis grounded in the user's own bank data. Statements (CSV today, PDF coming) ingest into a local DuckDB; tools query that DB. Everything runs in-process; **no data ever leaves the user's machine**.

Read [`spec.md`](./spec.md) for the full requirements and architectural context before making non-trivial changes.

## Build / test / run

This project uses [`uv`](https://docs.astral.sh/uv/). Requires Python 3.12+.

```bash
uv sync                          # install deps
uv run pytest                    # full test suite
uv run pytest tests/test_X.py    # single test file
uv run personal-finance          # boot the MCP server (stdio transport)
```

There is no separate lint/typecheck step yet.

## Code layout

```
src/personal_finance/
├── server.py                    # FastMCP server entry; registers all tools
├── config.py                    # data dir resolution (PERSONAL_FINANCE_DATA env, default ~/.personal-finance)
├── models.py                    # Pydantic Transaction model
├── db/
│   ├── connection.py            # connect(path); get_db() for tools
│   └── schema.py                # idempotent DDL: transactions + processing_log
├── ingest/
│   ├── pipeline.py              # ingest_folder() — scan, match profile, dedup, insert
│   ├── profile.py               # JSON profile loading + header-fingerprint matching
│   ├── csv_parser.py            # parse a CSV under a profile, normalize amounts
│   └── fingerprint.py           # file hash + per-transaction fingerprint
├── profiles/                    # shipped bank profiles (JSON)
├── categories/
│   ├── taxonomy.py              # the 14 unified categories
│   ├── mappings.json            # institution → unified + keyword regex rules
│   └── categorize.py            # apply mapping precedence to a Transaction
└── tools/                       # one module per MCP tool family
    ├── ingest.py                # ingest_statements()
    ├── transactions.py          # get_transactions(...)
    ├── spending.py              # _parse_period + get_spending_by_category
    ├── overview.py              # get_financial_overview — the dashboard
    ├── categories.py            # recategorize_all
    └── health.py                # get_data_freshness

tests/
├── fixtures/                    # anonymized CSV samples; NEVER real bank data
├── test_ingest.py               # parse + dedup
├── test_categories.py           # taxonomy + categorize precedence
├── test_periods.py              # period parser (calendar + rolling + DB-relative)
├── test_overview.py             # dashboard tool
├── test_profiles_more_banks.py  # Amex / Discover / Wells Fargo
├── test_tools.py                # transactions, spending, freshness
└── test_server.py               # FastMCP wiring (server name, tool list)
```

## How to add a new bank profile

1. Get a sample CSV (or anonymize the user's). Identify:
   - Column headers
   - Date format
   - Amount sign convention (does positive mean expense or income?)
   - Whether amounts have `$`, commas, or unusual encoding (BOM, etc.)
2. Create `src/personal_finance/profiles/{institution}_{account_type}.json`. Use [`chase_credit.json`](src/personal_finance/profiles/chase_credit.json) as the canonical example. Schema:
   ```json
   {
     "institution": "...",
     "account_type": "credit_card" | "checking" | "savings",
     "header_fingerprint": ["distinctive", "column", "names"],
     "columns": {
       "transaction_date": "...",
       "description": "...",
       "amount": "...",
       "category": "..."        // optional
     },
     "amount_sign": "negative_is_expense" | "positive_is_expense",
     "date_format": "%m/%d/%Y"
   }
   ```
   `header_fingerprint` must be a subset of the actual CSV headers. Pick distinctive ones so other banks' files don't accidentally match.
3. Add the bank to `src/personal_finance/categories/mappings.json` under `institution_mappings` — map every bank category string to one of the 14 unified categories in `taxonomy.py`. Anything mapped to `"Uncategorized"` will fall through to keyword rules (this is deliberate).
4. Add an **anonymized** fixture at `tests/fixtures/{institution}_{account_type}_sample.csv`. Use fake merchants/amounts but preserve every formatting quirk (BOM, multi-line cells, etc.).
5. Add tests in [`tests/test_profiles_more_banks.py`](tests/test_profiles_more_banks.py) following the existing pattern.
6. Run `uv run pytest`. Smoke-test against the user's real folder if available.
7. Document the new profile in [`docs/banks.md`](docs/banks.md).

## How to add or change a categorization rule

Edit `src/personal_finance/categories/mappings.json`. Two layers:

- `institution_mappings.{bank}.{their_category}` → one of the unified categories
- `keyword_rules`: ordered list of `{pattern: regex, category: unified}`. Patterns are case-insensitive and match against `description_clean` (uppercased, whitespace-collapsed).

Precedence: amount-sign shortcut (negative on credit card → Payments & Credits) > institution mapping > keyword rule > Uncategorized.

After editing, call `recategorize_all` via the MCP server to update existing rows. The user can also store a custom mappings file at `~/.personal-finance/categories.json` that fully replaces the shipped one.

## Conventions

- **Amount sign**: positive = expense, negative = income. Always. Per-bank flips happen in `csv_parser._parse_amount` driven by the profile's `amount_sign`.
- **Transaction fingerprint**: `SHA-256(date | amount.quantize(0.01) | description_clean | institution | account_type)`. This is the table PK; duplicate transactions are silently skipped.
- **File deduplication**: SHA-256 of file bytes lands in `processing_log`. Re-running ingest is idempotent.
- **Dates**: ISO 8601 (`YYYY-MM-DD`) everywhere outside the parser. Parse from bank-specific formats only.
- **Database file**: `~/.personal-finance/transactions.duckdb` by default; override with `PERSONAL_FINANCE_DATA` env var.

## Don'ts

- **Don't commit financial data.** `.gitignore` blocks `*.csv`, `*.pdf`, `*.duckdb` outside `tests/fixtures/`. If you bypass it, audit before pushing.
- **Don't use real fixtures.** Test fixtures must be anonymized — fake merchants, fake amounts, real *format quirks*.
- **Don't change the DuckDB schema without a migration plan.** `db/schema.py` is currently `CREATE IF NOT EXISTS`; that's enough for additive changes. For breaking changes you need a migration story.
- **Don't add Plaid or any third-party network call** without explicit opt-in. The product's wedge is *"your data stays on your machine."* See [`spec.md`](./spec.md) §5 NFR-1.
- **Don't add prescriptive financial advice** outputs without a disclaimer wrapper. Recommendations are allowed (see spec §3) but must carry the standard "not licensed financial advice" string.
- **Don't `git push --force`** to `main`. There's no PR workflow yet but linear history is the convention.
