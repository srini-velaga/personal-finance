# personal-finance

A self-hosted **MCP server** that gives any MCP-compatible AI agent (Claude Desktop, Cursor, ChatGPT, etc.) personal financial analysis grounded in your own data — **without that data ever leaving your machine**.

> Status: **v0 scaffold**. Server boots and exposes stub tools. Ingest, analysis, and recommendations are being built incrementally — see [spec](#spec).

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

- `get_spending_by_category(period)` — stub
- `get_data_freshness()` — stub

## Run locally

```bash
uv run personal-finance         # start the MCP server (stdio transport)
uv run pytest                   # run tests
```

## Roadmap

v1 (in progress):
- [x] FastMCP server scaffold + stub tools
- [ ] CSV/PDF statement ingestion (profile-based, header-fingerprint matching)
- [ ] DuckDB schema + transaction storage
- [ ] Core analysis tools: spending, cashflow, top merchants, recurring charges, MoM trend
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
