from __future__ import annotations

from graph.state import GraphState

from .mcp_client import call_analyze_stock_news


async def news_agent_node(state: GraphState) -> dict:
    """LangGraph node：把 router 決定的 stock_code 透過 MCP 交給 news_agent 的 MCP server 執行。"""
    stock_code = state.get("stock_code")
    if not stock_code:
        return {
            "final_response": "請提供股票代碼（例如 2330），我才能幫你分析新聞。",
        }

    result = await call_analyze_stock_news(stock_code)
    return {
        "result": result,
        "final_response": result["conclusion"],
    }
