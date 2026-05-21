# personal-finance

A self-hosted **MCP server** that gives any MCP-compatible AI agent (Claude Desktop, Cursor, ChatGPT, etc.) personal financial analysis grounded in your own data — **without that data ever leaving your machine**.

> Status: **v0.5 — dashboard view**. Single-call `get_financial_overview` returns headline cashflow, top categories, top merchants, recent transactions, and per-account activity for any month/quarter/year. Four banks covered via CSV (Chase, Amex, Discover, Wells Fargo). PDF parsing, budgets, debt, and recommendations are next — see [spec](#spec).

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
      "command": "uv",
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

Restart Claude Desktop. You should see `personal-finance` listed in the MCP servers menu with these tools:

- `ingest_statements(folder)` — scan a directory of CSVs into local DuckDB
- `recategorize_all()` — re-apply category rules after editing mappings
- `get_financial_overview(period?)` — single-call dashboard: headline cashflow, top categories, top merchants, recent activity, per-account summary
- `get_transactions(...)` — query stored transactions with filters
- `get_spending_by_category(period)` — category breakdown for a month / quarter / year
- `get_data_freshness()` — what's currently in your local DB

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

## Spec

Full requirements spec: [spec.md](spec.md).

## License

MIT
