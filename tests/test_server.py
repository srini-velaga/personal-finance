from personal_finance.server import mcp


def test_server_initialized():
    assert mcp.name == "personal-finance"


async def test_tools_registered_with_fastmcp():
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert names == {
        "ingest_statements",
        "get_transactions",
        "get_spending_by_category",
        "get_data_freshness",
    }
