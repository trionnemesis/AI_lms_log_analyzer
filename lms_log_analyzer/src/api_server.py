from __future__ import annotations
"""提供日誌分析 API 的 FastAPI 服務。"""

from typing import List

from fastapi import FastAPI
from pydantic import BaseModel

from .log_processor import analyse_lines
from .utils import save_state, STATE
from .vector_db import VECTOR_DB, embed

app = FastAPI()


class Logs(BaseModel):
    """送往 API 的日誌批次資料結構。"""

    # Raw log lines that should be processed in order
    logs: List[str]


class InvestigateQuery(BaseModel):
    """``/investigate`` 端點的查詢格式。"""

    log: str
    top_k: int = 5


@app.post("/analyze/logs")
async def analyze_logs(payload: Logs):
    """分析日誌並回傳結構化結果。

    參數
    ----
    payload:
        用戶送入的 :class:`Logs` 物件。

    回傳
    ----
    list[dict]
        每條選定日誌的分析結果列表。
    """

    return analyse_lines(payload.logs)


@app.post("/investigate")
async def investigate_log(query: InvestigateQuery):
    """搜尋與指定日誌相似的歷史案例。"""

    vec = embed(query.log)
    ids, dists = VECTOR_DB.search(vec, k=query.top_k)
    cases = VECTOR_DB.get_cases(ids)
    return [
        {"log": c.get("log"), "analysis": c.get("analysis"), "distance": d}
        for c, d in zip(cases, dists)
    ]


@app.on_event("shutdown")
def _shutdown() -> None:
    """應用停止前寫入狀態與向量資料。"""
    save_state(STATE)
    VECTOR_DB.save()
