from personal_finance.server import mcp
from personal_finance.tools import health, spending


def test_server_initialized():
    assert mcp.name == "personal-finance"


async def test_tools_registered_with_fastmcp():
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert "get_spending_by_category" in names
    assert "get_data_freshness" in names


def test_get_spending_by_category_stub():
    result = spending.get_spending_by_category("2026-04")
    assert result["period"] == "2026-04"
    assert "categories" in result


def test_get_data_freshness_stub():
    result = health.get_data_freshness()
    assert "server_version" in result
    assert result["accounts"] == []
