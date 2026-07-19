from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from graph.build import build_graph

app = FastAPI(title="台股多代理人分析系統", version="2.0.0")

_graph = build_graph()


class ChatRequest(BaseModel):
    message: str


@app.get("/", response_class=HTMLResponse)
def index():
    return """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>台股多代理人分析系統</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', sans-serif; background: #f0f2f5; color: #333; }
    .container { max-width: 860px; margin: 40px auto; padding: 0 16px; }
    h1 { text-align: center; margin-bottom: 28px; color: #1a1a2e; }
    .search-box { display: flex; gap: 10px; margin-bottom: 32px; }
    input { flex: 1; padding: 12px 16px; font-size: 16px; border: 2px solid #ddd; border-radius: 8px; outline: none; }
    input:focus { border-color: #4361ee; }
    button { padding: 12px 28px; background: #4361ee; color: #fff; border: none; border-radius: 8px; font-size: 16px; cursor: pointer; }
    button:hover { background: #3451d1; }
    #loading { display: none; text-align: center; padding: 40px; color: #666; font-size: 18px; }
    #result { display: none; }
    .meta { background: #fff; border-radius: 12px; padding: 20px 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,.08); }
    .meta h2 { font-size: 22px; margin-bottom: 10px; }
    .counts { display: flex; gap: 16px; margin-bottom: 12px; }
    .badge { padding: 6px 14px; border-radius: 20px; font-weight: bold; font-size: 14px; }
    .bull { background: #d4edda; color: #155724; }
    .bear { background: #f8d7da; color: #721c24; }
    .neutral { background: #e2e3e5; color: #383d41; }
    .conclusion { line-height: 1.7; color: #555; }
    .article { background: #fff; border-radius: 12px; padding: 20px 24px; margin-bottom: 14px; box-shadow: 0 2px 8px rgba(0,0,0,.06); }
    .article-title { font-size: 16px; font-weight: bold; margin-bottom: 8px; }
    .article-title a { color: #4361ee; text-decoration: none; }
    .article-title a:hover { text-decoration: underline; }
    .article-sentiment { display: inline-block; margin-bottom: 8px; }
    .article-summary { line-height: 1.7; color: #555; font-size: 15px; }
    .plain-reply { background: #fff; border-radius: 12px; padding: 20px 24px; line-height: 1.7; box-shadow: 0 2px 8px rgba(0,0,0,.06); }
    #error { display: none; background: #f8d7da; color: #721c24; padding: 16px; border-radius: 8px; margin-bottom: 20px; }
  </style>
</head>
<body>
  <div class="container">
    <h1>📈 台股多代理人分析系統</h1>
    <div class="search-box">
      <input type="text" id="messageInput" placeholder="輸入問題，例如：幫我看 2330 最近的新聞風向">
      <button onclick="chat()">送出</button>
    </div>
    <div id="error"></div>
    <div id="loading">⏳ 正在處理，請稍候...</div>
    <div id="result"></div>
  </div>

  <script>
    document.getElementById('messageInput').addEventListener('keydown', e => {
      if (e.key === 'Enter') chat();
    });

    async function chat() {
      const message = document.getElementById('messageInput').value.trim();
      if (!message) { alert('請輸入問題'); return; }

      document.getElementById('error').style.display = 'none';
      document.getElementById('result').style.display = 'none';
      document.getElementById('loading').style.display = 'block';

      try {
        const resp = await fetch('/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || '處理失敗');
        renderResult(data);
      } catch(e) {
        document.getElementById('error').textContent = '❌ ' + e.message;
        document.getElementById('error').style.display = 'block';
      } finally {
        document.getElementById('loading').style.display = 'none';
      }
    }

    function renderResult(data) {
      const d = data.result;

      // router 沒有命中任何 sub-agent，或 sub-agent 沒有回傳結構化結果時，顯示純文字回覆
      if (!d || !d.articles) {
        document.getElementById('result').innerHTML =
          `<div class="plain-reply">${data.final_response || ''}</div>`;
        document.getElementById('result').style.display = 'block';
        return;
      }

      const overall = d.overall_sentiment;
      const badgeClass = overall === '看漲' ? 'bull' : overall === '看跌' ? 'bear' : 'neutral';
      let html = `
        <div class="meta">
          <h2>${d.company}（${d.stock_code}）</h2>
          <div class="counts">
            <span class="badge bull">看漲 ${d.bullish_count} 篇</span>
            <span class="badge bear">看跌 ${d.bearish_count} 篇</span>
            <span class="badge ${badgeClass}">整體：${overall}</span>
          </div>
          <p class="conclusion">${d.conclusion}</p>
        </div>`;

      d.articles.forEach((a, i) => {
        const sc = a.sentiment === '看漲' ? 'bull' : 'bear';
        const dateStr = a.date ? new Date(a.date).toLocaleDateString('zh-TW', {year:'numeric',month:'2-digit',day:'2-digit'}) : '';
        html += `
          <div class="article">
            <div class="article-title">${i+1}. <a href="${a.url}" target="_blank" rel="noopener">${a.title}</a></div>
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
              <span class="badge ${sc} article-sentiment">${a.sentiment}</span>
              ${dateStr ? `<span style="color:#999;font-size:13px">📅 ${dateStr}</span>` : ''}
            </div>
            <p class="article-summary">${a.summary}</p>
          </div>`;
      });

      const el = document.getElementById('result');
      el.innerHTML = html;
      el.style.display = 'block';
    }
  </script>
</body>
</html>
"""


@app.post("/chat")
async def chat(req: ChatRequest):
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="請輸入問題")

    try:
        state = await _graph.ainvoke({"user_input": message})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"處理過程發生錯誤：{e}")

    return {
        "route": state.get("route"),
        "final_response": state.get("final_response"),
        "result": state.get("result"),
    }
