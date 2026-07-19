import json
import re
import socket

import requests
from bs4 import BeautifulSoup
from gnews import GNews
from googlenewsdecoder import gnewsdecoder
from langchain_core.tools import tool
from datetime import datetime
import twstock

# gnews（feedparser）跟 googlenewsdecoder 內部的 requests 呼叫都沒有帶 timeout，
# 一旦某個請求卡住就會無限期 hang 住整個 /chat 請求。設定全域 socket 預設 timeout，
# 讓這些沒帶 timeout 的呼叫也會在逾時後拋例外，而不是永遠卡住。
socket.setdefaulttimeout(15)

# 新聞若「真實發布日期」跟 Google News 回報的日期差超過這個天數，視為過期／被錯誤配對，直接捨棄。
_STALE_THRESHOLD_DAYS = 14

_DATE_META_KEYS = {
    "article:published_time",
    "og:article:published_time",
    "og:published_time",
    "pubdate",
    "publishdate",
    "publish-date",
    "date",
}

# 內文中常見的日期文字，例如「2022-04-28 17:18」「2026/07/10」
_DATE_TEXT_RE = re.compile(r"(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})(?:[ T](\d{1,2}):(\d{2}))?")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8",
}


def _company_name(stock_code: str) -> str:
    """查詢台股代碼對應的中文公司名，查無資料時回傳 None。"""
    info = twstock.codes.get(stock_code)
    return info.name if info else None


def _parse_gnews_date(date_str: str) -> datetime:
    try:
        return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z")
    except Exception:
        return datetime.min


def _resolve_real_url(url: str) -> str | None:
    """
    gnews 回傳的 url 沒裝 playwright 時仍是 news.google.com 的轉址連結，
    直接爬會抓到 Google 的空殼頁面而非真正文章。用 gnewsdecoder 解碼出
    真正的出版商網址，確保跟這則新聞的標題／日期對應到同一篇文章。
    """
    if "news.google.com" not in url:
        return url
    try:
        result = gnewsdecoder(url)
        if result.get("status"):
            return result.get("decoded_url")
    except Exception:
        pass
    return None


def _parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def _extract_published_at(soup: BeautifulSoup) -> datetime | None:
    """
    從文章頁面找出真正的發布時間，用來驗證 Google News 回報的日期是否可信
    （Google News 常常把舊文章重新推播，卻標成最近的日期）。
    """
    # 1) JSON-LD structured data（新聞網站最常見、也最準確的來源）
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except Exception:
            continue
        candidates = data if isinstance(data, list) else [data]
        for c in candidates:
            if isinstance(c, dict) and c.get("datePublished"):
                dt = _parse_iso(c["datePublished"])
                if dt:
                    return dt

    # 2) <meta> 標籤
    for tag in soup.find_all("meta"):
        key = (tag.get("property") or tag.get("name") or "").lower()
        if key in _DATE_META_KEYS:
            dt = _parse_iso(tag.get("content", ""))
            if dt:
                return dt

    # 3) 內文開頭常見的日期文字，當作最後手段
    text = soup.get_text(" ", strip=True)[:2000]
    m = _DATE_TEXT_RE.search(text)
    if m:
        y, mo, d, h, mi = m.groups()
        try:
            return datetime(int(y), int(mo), int(d), int(h or 0), int(mi or 0))
        except ValueError:
            return None

    return None


def _fetch_article(url: str, max_chars: int = 3000) -> tuple[str, datetime | None]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 必須在移除 <script> 之前抓日期，JSON-LD 就藏在 <script> 裡
        published_at = _extract_published_at(soup)

        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "figure"]):
            tag.decompose()
        paragraphs = soup.find_all("p")
        text = " ".join(
            p.get_text(strip=True)
            for p in paragraphs
            if len(p.get_text(strip=True)) > 30
        )
        content = text[:max_chars] if text else soup.get_text(separator=" ", strip=True)[:max_chars]
        return content, published_at
    except Exception as e:
        return f"[無法讀取文章內容: {e}]", None


@tool
def search_stock_news(stock_code: str) -> list[dict]:
    """
    根據台股代碼，從 Google News 取得最新 10 篇相關新聞，
    回傳包含標題、日期、連結和文章內容的清單。
    """
    company = _company_name(stock_code)
    if not company:
        return []  # 代碼不存在，讓 agent 層回報錯誤

    # Step 1: gnews 取最近 20 篇，排序後取最新 10 篇
    gn = GNews(language="zh-TW", country="TW", max_results=20, period="7d")
    try:
        raw = gn.get_news(company)
    except Exception:
        return []  # 逾時或網路錯誤，讓 agent 層回報查無新聞
    raw.sort(key=lambda a: _parse_gnews_date(a.get("published date", "")), reverse=True)

    results = []
    seen_urls: set[str] = set()

    for item in raw:
        if len(results) >= 10:
            break

        raw_title = item.get("title", "").strip()
        # 去掉標題尾端的 " - 來源名" 後綴
        clean_title = raw_title.rsplit(" - ", 1)[0].strip() if " - " in raw_title else raw_title
        date = item.get("published date", "")
        raw_url = item.get("url", "")
        real_url = _resolve_real_url(raw_url) if raw_url else None

        if not real_url or real_url in seen_urls:
            continue
        seen_urls.add(real_url)

        # Step 2: BeautifulSoup 爬取完整文章，並嘗試從頁面找出真正的發布日期
        content, published_at = _fetch_article(real_url)

        # Google News 有時會把舊文章重新推播並標成近期日期；
        # 若爬到的真實發布日期跟 Google 回報的日期差太多，代表這篇是過期新聞，直接跳過。
        if published_at is not None:
            if abs((published_at - datetime.now()).days) > _STALE_THRESHOLD_DAYS:
                continue
            date = published_at.strftime("%a, %d %b %Y %H:%M:%S GMT")

        results.append({
            "title": clean_title,
            "url": real_url,
            "date": date,
            "content": content,
        })

    return results
