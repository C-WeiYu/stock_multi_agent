from __future__ import annotations

import json
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate

from llm import get_llm
from tools import _company_name

from .state import GraphState

_STOCK_CODE_RE = re.compile(r"\b\d{4,6}\b")

_FALLBACK_REPLY = "目前我只能幫你分析台股個股的新聞情緒，請告訴我股票代碼，例如：「幫我看 2330 的新聞風向」。"


def _build_system_prompt(agents: dict) -> str:
    agent_lines = "\n".join(f"- {name}: {agent.description}" for name, agent in agents.items())
    return (
        "你是一個任務分派路由器（router），負責判斷使用者的問題應該交給哪一個 sub-agent 處理。\n"
        f"目前可用的 sub-agent：\n{agent_lines}\n\n"
        "請完成以下判斷：\n"
        "1. 判斷使用者的問題屬於哪一個 sub-agent；如果都不符合，agent 請填 \"none\"。\n"
        "2. 如果問題中有提到股票代碼（4-6 位數字），請擷取出來；沒有的話 stock_code 填 null。\n"
        "3. 如果 agent 是 \"none\"，請在 reply 欄位用繁體中文簡短說明你目前能處理什麼問題。\n\n"
        "請嚴格按照以下 JSON 格式回覆，不要加任何其他文字：\n"
        '{"agent": "news_agent 或 none", "stock_code": "2330 或 null", "reply": "..."}'
    )


def _parse_router_output(raw: str) -> dict:
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(raw[start:end])
    except Exception:
        pass
    return {}


def route(state: GraphState, agents: dict) -> dict:
    """router node 的實作：呼叫 LLM 判斷意圖、擷取股票代碼、決定要派給哪個 sub-agent。"""
    llm = get_llm()
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=_build_system_prompt(agents)),
        HumanMessage(content=state["user_input"]),
    ])
    response = (prompt | llm).invoke({})
    data = _parse_router_output(response.content.strip())

    agent_name = data.get("agent")
    if agent_name not in agents:
        agent_name = None

    stock_code = data.get("stock_code") or None

    # Fallback：LLM 若沒抓到股票代碼，直接用正則從原始輸入找
    if not stock_code:
        match = _STOCK_CODE_RE.search(state["user_input"])
        if match:
            stock_code = match.group()

    # 驗證股票代碼是否存在於 twstock 清單，不存在就視為沒有代碼
    if stock_code and not _company_name(stock_code):
        stock_code = None

    if agent_name is not None and not stock_code:
        return {
            "route": None,
            "router_reply": "請提供正確的台股代碼（4-6 位數字），我才能幫你查新聞，例如：「幫我看 2330 的新聞風向」。",
        }

    if agent_name is None:
        reply = data.get("reply") or _FALLBACK_REPLY
        return {"route": None, "router_reply": reply}

    return {"route": agent_name, "stock_code": stock_code}
