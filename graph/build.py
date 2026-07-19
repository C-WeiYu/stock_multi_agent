from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agents.registry import build_registry

from .router import route
from .state import GraphState


def _no_agent_node(state: GraphState) -> dict:
    return {"final_response": state.get("router_reply") or "抱歉，我無法處理這個問題。"}


def build_graph() -> CompiledStateGraph:
    """組出 router -> sub-agent -> END 的 LangGraph。"""
    agents = build_registry()

    def router_node(state: GraphState) -> dict:
        return route(state, agents)

    def select_next(state: GraphState) -> str:
        route_name = state.get("route")
        return route_name if route_name in agents else "no_agent"

    graph = StateGraph(GraphState)
    graph.add_node("router", router_node)
    graph.add_node("no_agent", _no_agent_node)
    for name, agent in agents.items():
        graph.add_node(name, agent.node)
        graph.add_edge(name, END)

    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router",
        select_next,
        {**{name: name for name in agents}, "no_agent": "no_agent"},
    )
    graph.add_edge("no_agent", END)

    return graph.compile()
