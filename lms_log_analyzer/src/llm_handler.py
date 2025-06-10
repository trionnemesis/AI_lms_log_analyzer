"""Gemini LLM 呼叫的極簡封裝。

正式版會透過 LangChain 與 Gemini 互動，此處僅依輸入文字產生
結構化 JSON，以便在無網路的測試環境模擬分析結果。
"""

from typing import List, Dict

import re


def _extract_entities(text: str) -> List[Dict]:
    """簡易擷取 IP 與使用者名稱為實體。"""
    entities: List[Dict] = []
    for ip in re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", text):
        entities.append({"id": f"ip_{ip}", "label": "IP", "properties": {"address": ip}})
    m = re.search(r"user(?:name)?[=:]?\s*(\w+)", text, re.I)
    if m:
        user = m.group(1)
        entities.append({"id": f"user_{user}", "label": "User", "properties": {"name": user}})
    return entities


def llm_analyse(payloads: List[Dict]) -> List[Dict]:
    """回傳結構化 JSON，模擬 Gemini 的安全分析結果。"""

    results: List[Dict] = []
    for payload in payloads:
        line = payload.get("alert", {}).get("original_log", "")
        entities = _extract_entities(line)
        attack_type = "Unknown"
        lower = line.lower()
        if "or 1=1" in lower or "union select" in lower:
            attack_type = "SQL Injection"
        elif "/etc/passwd" in lower:
            attack_type = "Sensitive File Access"
        elif "nmap" in lower:
            attack_type = "Port Scan"
        is_attack = attack_type != "Unknown"
        relations: List[Dict] = []
        if len(entities) >= 2:
            relations.append({"start_id": entities[0]["id"], "end_id": entities[1]["id"], "type": "RELATED"})
        results.append({
            "is_attack": is_attack,
            "attack_type": attack_type,
            "entities": entities,
            "relations": relations,
        })
    return results
