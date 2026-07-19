from __future__ import annotations

from typing import Any, Optional, TypedDict


class GraphState(TypedDict, total=False):
    """整個 LangGraph 在節點之間傳遞的共用狀態。"""

    user_input: str  # 使用者原始輸入（自然語言）

    # --- router 產出 ---
    route: Optional[str]  # 命中的 sub-agent 名稱；None 代表沒有 sub-agent 能處理
    stock_code: Optional[str]  # router 從輸入中擷取出的股票代碼
    router_reply: Optional[str]  # route 為 None 時，router 直接給使用者的回覆

    # --- sub-agent 產出 ---
    result: Optional[dict[str, Any]]  # sub-agent 執行後的結構化結果（給前端渲染用）
    final_response: Optional[str]  # 最終要顯示給使用者的一段文字結論
