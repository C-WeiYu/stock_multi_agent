from __future__ import annotations

from graph.state import GraphState

from .skill import run_stock_news_agent


def news_agent_node(state: GraphState) -> dict:
    """LangGraph node：把 router 決定的 stock_code 交給 news_agent 的 skill 執行。"""
    stock_code = state.get("stock_code")
    if not stock_code:
        return {
            "final_response": "請提供股票代碼（例如 2330），我才能幫你分析新聞。",
        }

    result = run_stock_news_agent(stock_code)
    return {
        "result": result,
        "final_response": result["conclusion"],
    }
