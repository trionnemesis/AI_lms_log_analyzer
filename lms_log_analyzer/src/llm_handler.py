"""LangChain Gemini Pro 封裝。"""

from __future__ import annotations

import json
from typing import List, Dict

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
import re

from .. import config

_SYSTEM_PROMPT = (
    "你是資安日誌分析助手，請依使用者輸入判斷是否為攻擊並輸出 JSON。\n"
    "必須僅回傳如下格式："
    "{\"is_attack\": bool, \"attack_type\": str, \"entities\": list, \"relations\": list}"
)


def _extract_entities(text: str) -> List[Dict]:
    """簡易擷取 IP 與使用者名稱為實體 (供 GraphRetrievalTool 使用)。"""
    entities: List[Dict] = []
    for ip in re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", text):
        entities.append({"id": f"ip_{ip}", "label": "IP", "properties": {"address": ip}})
    m = re.search(r"user(?:name)?[=:]?\s*(\w+)", text, re.I)
    if m:
        user = m.group(1)
        entities.append({"id": f"user_{user}", "label": "User", "properties": {"name": user}})
    return entities


def _chat() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=config.LLM_MODEL_NAME,
        google_api_key=config.GOOGLE_API_KEY or config.GEMINI_API_KEY,
    )


def llm_analyse(payloads: List[Dict]) -> List[Dict]:
    """使用 Gemini Pro 產生安全分析結果。"""

    chat = _chat()
    results: List[Dict] = []
    for payload in payloads:
        line = payload.get("alert", {}).get("original_log", "")
        examples = payload.get("examples", [])
        graph = payload.get("graph", {})
        user_prompt = (
            f"Log: {line}\n"
            f"Examples: {examples}\n"
            f"Graph: {json.dumps(graph, ensure_ascii=False)}"
        )
        messages = [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=user_prompt)]
        try:
            response = chat.invoke(messages)
            data = json.loads(response.content)
        except Exception:
            data = {}
        results.append(data)
    return results
