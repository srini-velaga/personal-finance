# Personal Financial Guidance Tool — Requirements Spec (v0.1)

> **Status**: Draft spec for a **clean-slate, ground-up build**. The existing repo (`financial-insights-skill`) is in a confusing state and will be **archived in full**. No code, schemas, profiles, configs, or files are reused. v0 is referenced only as a source of *learnings* (what worked conceptually) — never as a starting point. The new project lives in a fresh repo.
> **Date**: 2026-05-21
> **Owner**: Srini Velaga

---

## 1. Context

### Why rebuild?
The current repo (`fin_insights` Python package + Claude Code skill) is a profile-based statement parser that ingests CSV/PDF bank exports into DuckDB and exposes spending insights. It works for its narrow scope but:
- It's a **Claude Code skill** — locked to one agent host. Cursor/ChatGPT/etc. can't use it.
- It's **statement-only** — no live balances, no goals, no debt/investment view.
- Its analysis layer (`insights`, `cashflow`, `recommend`) is bolted on top of a parser, not designed as a coherent guidance product.

### What changed in the market (last ~3 weeks)
The "agent-native personal finance" category was created *while this repo was being built*:
- **[Era](https://finance.yahoo.com/markets/options/articles/era-becomes-first-personal-finance-140000473.html)** (May 6, 2026) — first personal-finance MCP connector in Anthropic's Claude Directory. Plaid-powered, hosted, agent-agnostic.
- **[ChatGPT Personal Finance](https://openai.com/index/personal-finance-chatgpt/)** (May 15, 2026) — OpenAI + Plaid, 12,000+ institutions, first-party.

Both are **hosted services** that proxy financial data through their servers. Neither offers a self-hosted/local-data option.

### Intended outcome
A self-hosted **MCP server** that any MCP-compatible agent (Claude, Cursor, ChatGPT, etc.) can connect to, giving its user personal financial analysis grounded in their own data — without that data ever leaving their machine.

---

## 2. Positioning & Wedge

| Dimension | Era / ChatGPT Finance | This tool |
|---|---|---|
| Hosting | SaaS (their servers) | Self-hosted (user's machine) |
| Data residency | Vendor cloud | Local disk only |
| Plaid required | Yes | Optional. When used, Plaid pulls **statements/transactions down to the user's machine** — it is not a live SaaS feed. |
| Agent lock-in | Claude/ChatGPT specific | Any MCP client |
| Scope of guidance | Spending + general advice | Spending → budgeting → debt → (later) investments |
| Audience | General consumers | Power users / privacy-conscious / self |

**One-line positioning**: *"The personal-finance MCP server for people who won't hand their bank data to a startup."*

**Non-goals as positioning**: Not a consumer product. Not a SaaS. Not a replacement for licensed financial advice.

---

## 3. Audience & Use Cases

**Primary user (v1)**: Srini, then privacy-conscious power users who can run an MCP server **and want real financial clarity and guidance** (not just dashboards).

**Canonical use cases the agent should handle well**:
1. *"What did I spend on dining last month vs. average?"* — categorized spending analysis
2. *"Show me my cashflow for Q1."* — income vs. spending across all accounts
3. *"Am I on track for my $20k emergency fund by year-end?"* — goal tracking
4. *"Which card should I have used for this $400 grocery run?"* — reward optimization (already works in v0)
5. *"If I throw an extra $500/mo at my highest-APR card, when am I debt-free?"* — debt payoff modeling
6. *"What recurring subscriptions am I paying for?"* — subscription detection
7. *"How has my savings rate trended over 12 months?"* — longitudinal analysis

**Advice depth**: **Analysis + recommendations** — surface facts, patterns, projections, *and* concrete suggestions ("pay off the 22% APR card first; you'd save $1,400/yr at your current cashflow"). Recommendations reason over the user's actual data so they are specific and grounded, not generic.

**Regulatory framing**: Every recommendation tool output is wrapped with a standard disclaimer string (e.g., *"This is informational analysis based on your data, not licensed financial advice."*). Implemented once as a shared wrapper in `src/financial_insights/recommend/`, applied uniformly. Lightweight, future-proofs the tool against distribution.

---

## 4. Functional Requirements

### v1 scope (MVP)
**Accounts in scope**: Credit cards + checking/savings, **plus user-entered static values for investments / retirement / real estate** to compute a net-worth view. Static values means the user types a number into a YAML config (e.g., `brokerage: 45000`); the tool reads it but doesn't sync or analyze it.
**Out of scope for v1**: *Live* brokerage/retirement data via APIs, real-estate valuation, crypto tracking, mortgage amortization. These move to v2.

#### 4.1 Data ingestion
- **FR-1.1**: Ingest statement files (CSV + PDF) from a user-specified folder. Profile-based parser, header-fingerprint matching. (Carries forward conceptually from v0; reimplemented.)
- **FR-1.2**: Optional Plaid integration. User provides their own Plaid client ID/secret (BYO-keys). Tokens stored encrypted on local disk. **Plaid's role is to download statements/transactions to the local machine** — once on disk, the ingest path is identical to the file-drop flow. No live cloud feed.
- **FR-1.3**: Auto-profile generation for unknown bank CSVs via LLM-assisted header inspection (existing capability worth keeping).
- **FR-1.4**: LLM-assisted PDF parsing for unknown banks (existing capability worth keeping).
- **FR-1.5**: Two-layer dedup: file-hash + transaction-fingerprint (existing approach, keep).

#### 4.2 Normalization
- **FR-2.1**: Unified category taxonomy — start small (a handful of core buckets like Food, Transport, Bills, Income, Transfers) and **extend organically** as real data exposes gaps. Do not lock a fixed taxonomy upfront.
- **FR-2.2**: Amount sign convention: positive = expense, negative = income. Normalized regardless of bank format.
- **FR-2.3**: Recurring transaction detection (merchant + cadence + amount tolerance). New in v1.
- **FR-2.4**: Subscription identification (subset of recurring with monthly/annual cadence).

#### 4.3 Analysis primitives (MCP tools exposed to agents)
- **FR-3.1**: `get_spending_by_category(period, account?)` — category breakdown
- **FR-3.2**: `get_cashflow(period)` — income vs spending vs savings rate
- **FR-3.3**: `get_top_merchants(period, n)` — merchant spending leaderboard
- **FR-3.4**: `get_recurring_charges()` — subscriptions and recurring bills
- **FR-3.5**: `get_transactions(filters)` — raw query with date/amount/category/merchant filters
- **FR-3.6**: `month_over_month(category?)` — trend analysis
- **FR-3.7**: `recommend_card_for_purchase(category, amount)` — card reward optimization (carry from v0)
- **FR-3.8**: `get_data_freshness()` — when was each account last updated

#### 4.4 Budgeting & goals
- **FR-4.1**: User defines budgets per category (declarative config file, agent-editable).
- **FR-4.2**: `get_budget_status(period)` — actuals vs. budget per category.
- **FR-4.3**: User defines savings goals (target amount + date + funding account).
- **FR-4.4**: `get_goal_progress(goal_id)` — projection based on current trajectory.

#### 4.5 Debt management
- **FR-5.1**: Track credit card balances + APRs (user-provided config, since APR isn't in transaction data).
- **FR-5.2**: `project_debt_payoff(strategy, extra_payment)` — avalanche/snowball/custom; returns months-to-zero + total interest.
- **FR-5.3**: `compare_payoff_strategies()` — side-by-side scenarios.

#### 4.6 Recommendations layer
Every recommendation tool returns: (a) the suggestion, (b) the quantified upside in dollars/time, (c) the data points that justified it, (d) a standard disclaimer string (applied uniformly via a shared wrapper — see §3).

- **FR-6.1**: `recommend_debt_strategy()` — based on the user's actual APRs and balances, suggest avalanche vs. snowball and projected savings.
- **FR-6.2**: `recommend_budget_adjustments()` — flag categories where actuals systematically exceed budget and suggest realistic targets.
- **FR-6.3**: `recommend_savings_opportunities()` — identify recurring subscriptions, duplicate services, or category overspend vs. peer benchmarks (peer data is generic, not personal).
- **FR-6.4**: `recommend_card_for_purchase` — already in FR-3.7; categorized here as a recommendation tool.
- **FR-6.5**: `recommend_emergency_fund_target()` — based on observed monthly expenses, suggest a target and time-to-reach at current savings rate.

### v2 scope (post-MVP, deferred)
- Investment/brokerage data (Plaid Investments product)
- Net worth tracking
- Retirement / FIRE projections
- Tax-lot awareness
- Multi-user / household support

---

## 5. Non-Functional Requirements

| ID | Requirement | Rationale |
|---|---|---|
| NFR-1 | All financial data persists only on the user's local disk. No telemetry, no cloud sync. | Core wedge. |
| NFR-2 | Plaid tokens (if used) encrypted at rest with OS-keychain-backed key. | Privacy promise must extend to credentials. |
| NFR-3 | Works offline once initial data is loaded. | No hard dependency on network for analysis. |
| NFR-4 | MCP server boots in <2s; tool calls return in <500ms p95 for queries over <100k transactions. | Agent UX. |
| NFR-5 | Reproducible install via `uv` or `pipx` / single binary. | Power-user audience tolerates CLI but not yak-shaving. |
| NFR-6 | Open source (MIT or Apache-2.0). | Trust + the audience. |
| NFR-7 | Recommendations must be grounded in the user's actual data, never generic. Every recommendation tool result is wrapped with the standard disclaimer (see §3). | Specificity is the value over Era/ChatGPT; disclaimer future-proofs against distribution. |

---

## 6. Architecture Sketch

```
┌──────────────────────────────────────────────────────────────┐
│   Agent (Claude, Cursor, ChatGPT, etc.) via MCP protocol     │
└────────────────────────────┬─────────────────────────────────┘
                             │ stdio / HTTP+SSE
┌────────────────────────────▼─────────────────────────────────┐
│   MCP Server  (this project)                                 │
│   ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│   │  Tools layer │  │ Analysis     │  │ Ingestion       │   │
│   │  (FR-3..5)   │  │ (DuckDB SQL) │  │ (profiles, PDF) │   │
│   └──────────────┘  └──────────────┘  └─────────────────┘   │
│   ┌──────────────────────────────────────────────────────┐  │
│   │            DuckDB (single-file, local)               │  │
│   │  transactions │ accounts │ budgets │ goals │ debt    │  │
│   └──────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
        ▲                       ▲                      ▲
        │ (optional)            │                      │
   ┌────┴────┐           ┌──────┴───────┐       ┌──────┴──────┐
   │  Plaid  │           │ Statement    │       │ User config │
   │  (BYO)  │           │ files folder │       │ (YAML/JSON) │
   └─────────┘           └──────────────┘       └─────────────┘
```

### Tech stack (locked)

- **Language**: **Python 3.12+**. Rationale: most mature ecosystem for this workload — plaid-python, pdfplumber, DuckDB Python bindings all battle-tested.
- **MCP framework**: **[FastMCP](https://www.stainless.com/mcp/mcp-sdk-comparison-python-vs-typescript-vs-go-implementations/)** (wraps the official Anthropic Python MCP SDK). De facto standard in the Python MCP ecosystem. Decorator API (`@mcp.tool()`), JSON schema inferred from type hints, ~70% less boilerplate than raw SDK. Uses pydantic for tool argument validation.
- **Storage**: **DuckDB** (single-file, OLAP-fast). Aligns with the analytical query shape (group-by month/category, window functions for trends, joins across transactions/budgets/goals).
- **PDF parsing**: **pdfplumber** (text + table extraction) + LLM fallback for unknown bank layouts.
- **Plaid**: **`plaid-python`** SDK, optional dependency, lazy-imported. User provides Plaid client ID/secret for sandbox + dev testing.
- **Config**: **YAML** files as the source of truth for user-editable data (budgets, goals, debt accounts, static net-worth values). MCP tools read and write the same YAML; user can also edit it directly.
- **Output format**: **Plain JSON / tabular tool results.** Claude Desktop auto-renders charts from tabular results (Altair/Vega-Lite). No server-side chart rendering in v1. MCP Apps (interactive HTML) deferred to v2 if needed.
- **Env mgmt**: `uv`.
- **Testing**: `pytest` with anonymized fixtures. Raw statements from v0's local data may be reused as test inputs.

### Data model (initial sketch)
- `transactions` — keep v0 schema; add `is_recurring`, `recurring_group_id`
- `accounts` — new: account metadata, balances (from Plaid or user input), APR, credit limit
- `budgets` — category, period, amount, start/end
- `goals` — name, target_amount, target_date, funding_account, current_amount
- `debt_accounts` — account_id, apr, min_payment, current_balance
- `recurring_groups` — merchant pattern, cadence, typical amount
- `processing_log`, `analysis_cache`, `session_log` — carry from v0

---

## 7. Out of Scope (explicitly)

- Hosted/SaaS deployment of any kind
- Mobile app or web UI (agents *are* the UI)
- Bill pay, money movement, account opening — read-only forever
- Tax filing / TurboTax-style guidance
- Multi-user / shared households (v1)
- Investment, retirement, crypto, real estate analysis (v2)
- **Licensed** financial advice. Recommendations are allowed and encouraged (see FR-6.x), but always with the disclaimer that this is not advice from a licensed fiduciary.

---

## 8. Open Questions / Decisions

All but one are now resolved:

1. ~~**Language**~~ — **Python 3.12+ + FastMCP.**
2. ~~**Storage engine**~~ — **DuckDB.**
3. ~~**Chart/UX output**~~ — **JSON tabular results; Claude Desktop auto-renders charts via Altair/Vega-Lite.** MCP Apps (interactive HTML) deferred to v2.
4. ~~**Config UX**~~ — YAML files as source of truth; MCP tools read/write the same YAML; user can edit directly.
5. ~~**Plaid testing**~~ — user (Srini) provides Plaid API keys for sandbox + dev.
6. ~~**Migration from v0**~~ — start fresh. v0 raw statements available as test inputs; no code/schema reuse.
7. ~~**Disclaimer / regulatory framing**~~ — standard disclaimer wrapper applied to every recommendation tool output (see §3 and FR-6 layer).
8. **Distribution channel** — *still open.* PyPI / GitHub releases / `uv tool install` / Docker. Decide before v1 release; not v1-development-blocking. Personal use during build will be via local editable install (`uv pip install -e .`).

---

## 9. Success Criteria (verification for v1)

The build is "done" for v1 when:
- [ ] Srini connects the MCP server to Claude Desktop and Cursor; both see the tools.
- [ ] Statement files in a folder are ingested with zero per-bank config for the 7 banks v0 supported.
- [ ] A previously-unsupported bank statement is ingested in <2 minutes with agent-assisted profile generation.
- [ ] The 7 canonical use cases (§3) all work end-to-end through an agent conversation, using only this MCP server's tools.
- [ ] A budget overrun and a debt-payoff projection produce numerically correct results, verified against hand-computed cases.
- [ ] No network call leaves the machine unless the user opts into Plaid.
- [ ] All tests pass on a fresh clone with `uv sync && uv run pytest`.

---

## 10. Critical Files (when build starts — not now)

**Clean-slate**: new repo, new package name (TBD), no files copied from v0. v0 is for *conceptual* reference only — read it for design intuition, then close the tab.

**Project name**: `financial-insights` (Python package: `financial_insights`)

Initial layout:
- `pyproject.toml` — package `financial-insights`, dependencies pinned via `uv`
- `src/financial_insights/server.py` — FastMCP server entry point (`@mcp.tool()` registrations)
- `src/financial_insights/tools/` — one module per tool group: `spending.py`, `cashflow.py`, `budgets.py`, `goals.py`, `debt.py`, `recurring.py`
- `src/financial_insights/recommend/` — recommendation logic + shared disclaimer wrapper (`with_disclaimer()` decorator)
- `src/financial_insights/db/` — DuckDB connection mgmt, schema, migrations
- `src/financial_insights/ingest/` — profile-based parsing + pdfplumber + LLM fallback
- `src/financial_insights/plaid/` — optional Plaid client (lazy-imported, only loaded if creds present)
- `src/financial_insights/config/` — YAML loaders for budgets, goals, debt accounts, static net-worth values
- `tests/` — pytest, anonymized fixtures
- `README.md` — install steps, MCP client config snippet (Claude Desktop / Cursor), privacy promise
- `LICENSE` — MIT or Apache-2.0 (TBD)

---

*End of spec. Next step: review, refine, and only then begin implementation.*
