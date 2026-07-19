from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from graph.state import GraphState

NodeFn = Callable[[GraphState], dict]


@dataclass(frozen=True)
class SubAgent:
    name: str
    description: str  # 給 router LLM 看的說明，用來判斷這個 sub-agent 適合處理什麼問題
    node: NodeFn


def build_registry() -> dict[str, SubAgent]:
    """組出目前系統中所有可被 router 派工的 sub-agent。

    要新增 sub-agent（例如技術面分析、基本面分析）時，
    只需要在這裡多註冊一筆，router 的 prompt 會自動帶入新的選項。
    """
    from agents.news_agent.node import news_agent_node

    agents = [
        SubAgent(
            name="news_agent",
            description=(
                "分析指定台股個股最近的新聞，統計看漲/看跌情緒並給出整體結論。"
                "適用於使用者想知道某檔股票新聞風向、市場情緒的問題。"
            ),
            node=news_agent_node,
        ),
    ]
    return {agent.name: agent for agent in agents}
