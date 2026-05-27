# personal-finance

A self-hosted **MCP server** that gives any MCP-compatible AI agent (Claude Desktop, Cursor, ChatGPT, etc.) personal financial analysis grounded in your own data — **without that data ever leaving your machine**.

> Status: **v0.6 — period flexibility + docs**. `get_financial_overview` now defaults to a rolling 12-month window and accepts `ytd`, `last_30_days`, `last_90_days`, `last_12_months`, `all` in addition to calendar periods. Four banks covered via CSV (Chase, Amex, Discover, Wells Fargo). PDF parsing, budgets, debt, and recommendations are next — see [spec](spec.md).

## Why this exists

Era and ChatGPT Personal Finance (both shipped May 2026) require you to hand your bank credentials to a third-party SaaS. This tool is the privacy-first alternative: it runs on your machine, stores data in a local DuckDB file, and never phones home.

## Install

Requires Python 3.12+ and [`uv`](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/srini-velaga/personal-finance.git
cd personal-finance
uv sync
```

## Connect to Claude Desktop

Add this to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "personal-finance": {
      "command": "/opt/homebrew/bin/uv",
      "args": [
        "--directory",
        "/Users/YOU/Documents/personal/personal-finance",
        "run",
        "personal-finance"
      ]
    }
  }
}
```

> **Use the absolute path to `uv`.** Claude Desktop on macOS launches with a minimal `PATH` (no Homebrew). `which uv` will tell you the right path; on Apple Silicon it's usually `/opt/homebrew/bin/uv`.

**Fully quit Claude Desktop** (Cmd+Q — not just close the window) and reopen. You should see `personal-finance` listed in the MCP servers menu with these tools:

- `ingest_statements(folder)` — scan a directory of CSVs into local DuckDB
- `recategorize_all()` — re-apply category rules after editing mappings
- `get_financial_overview(period?)` — single-call dashboard: headline cashflow, top categories, top merchants, recent activity, per-account summary
- `get_transactions(...)` — query stored transactions with filters
- `get_spending_by_category(period)` — category breakdown for a month / quarter / year
- `get_data_freshness()` — what's currently in your local DB

## Try it

Once connected in Claude Desktop, these are real prompts that work end-to-end:

- *"Ingest the statements in ~/Documents/personal/financial-statements/statements"*
- *"Give me a financial overview"* — defaults to the last 12 months
- *"How was Q4 2025?"* / *"Show me year-to-date"* / *"Last 90 days?"*
- *"Show me 2025 spending by category"*
- *"What were my top food merchants last quarter?"*
- *"Find every Amazon transaction over $50 in 2025"*

If a category looks wrong, edit `~/.personal-finance/categories.json` (or the shipped `src/personal_finance/categories/mappings.json`) and ask Claude to *"recategorize everything"*.

## Data location

By default the local DB lives at `~/.personal-finance/transactions.duckdb`. Override with the `PERSONAL_FINANCE_DATA` env var if you want it elsewhere.

## Run locally

```bash
uv run personal-finance         # start the MCP server (stdio transport)
uv run pytest                   # run tests
```

## Roadmap

v1 (in progress):
- [x] FastMCP server scaffold + stub tools
- [x] DuckDB schema + transaction storage
- [x] CSV statement ingestion (profile-based, header-fingerprint matching)
- [x] One bank profile shipped (Chase credit)
- [x] `get_transactions`, `get_spending_by_category`, `get_data_freshness` tools
- [x] Unified category taxonomy + keyword mappings + `recategorize_all` tool
- [x] Bank profiles: Chase, Amex, Discover, Wells Fargo (credit CSVs)
- [x] `get_financial_overview()` dashboard tool — single-call snapshot
- [ ] PDF statement parsing (pdfplumber + LLM fallback) — for BofA and PDF-only flows
- [ ] Chase checking + other checking-account profiles
- [ ] Core analysis tools: cashflow, top merchants, recurring charges, MoM trend
- [ ] Budgeting & goals (YAML config + tools)
- [ ] Debt payoff modeling
- [ ] Recommendation layer with standard disclaimer wrapper
- [ ] Optional Plaid integration (BYO API keys, statement-downloader role)

v2 (later):
- Investments / retirement / FIRE modeling
- MCP Apps (interactive HTML) for richer visualizations

## Privacy

- All financial data persists only on your local disk
- No telemetry, no cloud sync, no third-party servers
- Plaid is **optional** and uses your own API keys; tokens encrypted at rest
- Recommendations are informational — **not licensed financial advice**

## More docs

- [Full spec](spec.md) — wedge, requirements, architecture
- [AGENTS.md](AGENTS.md) — guidance for AI agents working in this repo (code layout, conventions, how to add a bank)
- [docs/banks.md](docs/banks.md) — per-bank profile reference (formats, quirks, what's been tested)

## License

MIT
