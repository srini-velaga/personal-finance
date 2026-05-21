"""FastMCP server entry point for personal-finance."""

from fastmcp import FastMCP

from personal_finance.tools import categories, health, ingest, spending, transactions

mcp: FastMCP = FastMCP("personal-finance")

mcp.tool(ingest.ingest_statements)
mcp.tool(categories.recategorize_all)
mcp.tool(transactions.get_transactions)
mcp.tool(spending.get_spending_by_category)
mcp.tool(health.get_data_freshness)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
