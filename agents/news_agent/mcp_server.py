from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from mcp.server.fastmcp import FastMCP

from llm import get_llm
from tools import search_stock_news, _company_name

mcp = FastMCP("news-agent")


def _summarize_and_judge(llm, title: str, content: str, company: str) -> dict:
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=(
            "你是一位專業的台股財經分析師。請根據以下新聞內容，完成兩件事：\n"
            "1. 用繁體中文寫一段 50-100 字的摘要。\n"
            "2. 判斷這篇新聞對該股票是「看漲」還是「看跌」，只能選其中一個。\n\n"
            "請嚴格按照以下 JSON 格式回覆，不要加任何其他文字：\n"
            '{"summary": "...", "sentiment": "看漲"}'
            "\n或\n"
            '{"summary": "...", "sentiment": "看跌"}'
        )),
        HumanMessage(content=(
            f"公司：{company}\n"
            f"新聞標題：{title}\n\n"
            f"新聞內容：\n{content}"
        )),
    ])

    chain = prompt | llm
    response = chain.invoke({})
    raw = response.content.strip()

    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            data = json.loads(raw[start:end])
            summary = data.get("summary", raw)
            sentiment = data.get("sentiment", "看跌")
            if sentiment not in ("看漲", "看跌"):
                sentiment = "看漲" if "看漲" in raw else "看跌"
        else:
            raise ValueError("no JSON found")
    except Exception:
        summary = raw[:200]
        sentiment = "看漲" if "看漲" in raw else "看跌"

    return {"summary": summary, "sentiment": sentiment}


@mcp.tool()
def analyze_stock_news(stock_code: str) -> dict[str, Any]:
    """分析指定台股個股最近的新聞，統計看漲/看跌情緒並給出整體結論。"""
    company = _company_name(stock_code)
    llm = get_llm()

    if not company:
        return {
            "stock_code": stock_code,
            "company": stock_code,
            "articles": [],
            "bullish_count": 0,
            "bearish_count": 0,
            "overall_sentiment": "無資料",
            "conclusion": f"查無股票代碼「{stock_code}」，請確認代碼是否正確。",
        }

    raw_news: list[dict] = search_stock_news.invoke({"stock_code": stock_code})

    if not raw_news:
        return {
            "stock_code": stock_code,
            "company": company,
            "articles": [],
            "bullish_count": 0,
            "bearish_count": 0,
            "overall_sentiment": "無資料",
            "conclusion": f"找不到「{company}」的近期新聞。",
        }

    articles = []
    for item in raw_news:
        result = _summarize_and_judge(llm, item["title"], item["content"], company)
        articles.append({
            "title": item["title"],
            "url": item["url"],
            "date": item.get("date", ""),
            "summary": result["summary"],
            "sentiment": result["sentiment"],
        })

    bullish_count = sum(1 for a in articles if a["sentiment"] == "看漲")
    bearish_count = len(articles) - bullish_count
    overall = "看漲" if bullish_count > bearish_count else ("看跌" if bearish_count > bullish_count else "中性")

    summary_text = "\n".join(
        f"{i+1}. [{a['sentiment']}] {a['summary']}"
        for i, a in enumerate(articles)
    )
    conclusion_prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content="你是一位專業的台股財經分析師，請根據以下多篇新聞摘要，用繁體中文寫出一段 100-150 字的整體市場情緒總結。"),
        HumanMessage(content=(
            f"股票：{company}（{stock_code}）\n\n"
            f"各篇新聞摘要：\n{summary_text}\n\n"
            f"看漲：{bullish_count} 篇，看跌：{bearish_count} 篇。\n"
            "請給出整體判斷。"
        )),
    ])
    conclusion_chain = conclusion_prompt | llm
    conclusion_resp = conclusion_chain.invoke({})
    conclusion = conclusion_resp.content.strip()

    return {
        "stock_code": stock_code,
        "company": company,
        "articles": articles,
        "bullish_count": bullish_count,
        "bearish_count": bearish_count,
        "overall_sentiment": overall,
        "conclusion": conclusion,
    }


if __name__ == "__main__":
    mcp.run()
