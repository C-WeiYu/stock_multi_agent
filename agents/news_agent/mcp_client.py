from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

_SERVER_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=["-m", "agents.news_agent.mcp_server"],
    cwd=str(_PROJECT_ROOT),
)


async def call_analyze_stock_news(stock_code: str) -> dict[str, Any]:
    """以 MCP client 身分啟動 news_agent 的 MCP server（stdio），呼叫 analyze_stock_news tool。"""
    async with stdio_client(_SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("analyze_stock_news", {"stock_code": stock_code})

            if result.isError:
                text = "".join(c.text for c in result.content if hasattr(c, "text"))
                raise RuntimeError(f"MCP tool 執行失敗：{text}")

            if result.structuredContent is not None:
                return result.structuredContent

            for block in result.content:
                if hasattr(block, "text"):
                    return json.loads(block.text)

            return {}
