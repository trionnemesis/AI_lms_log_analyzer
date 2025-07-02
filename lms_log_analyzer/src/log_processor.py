"""日誌處理流程核心（供單元測試使用）。

此模組以最精簡的方式實作 README 所述的多層過濾漏斗，每一階段都會進一步
篩減待送入語言模型的日誌行。除了向量搜尋外，也透過 ``GraphRetrievalTool``
查詢 Neo4j 子圖作為 GraphRAG 的額外脈絡。"""
from __future__ import annotations

from pathlib import Path
from typing import List, Dict

from opensearchpy import OpenSearch

from .. import config
from .utils import logger, STATE, save_state
from .log_parser import fast_score
from .vector_db import VECTOR_DB, embed
from .llm_handler import llm_analyse
from . import wazuh_api
from .graph_builder import GraphBuilder
from .graph_retrieval_tool import GraphRetrievalTool


# Initialize once so processed events accumulate into Neo4j
GRAPH_BUILDER = GraphBuilder()
GRAPH_RETRIEVER = GraphRetrievalTool(GRAPH_BUILDER)

# Lazily initialized OpenSearch client for polling logs
_os_client: OpenSearch | None = None


def _get_os_client() -> OpenSearch:
    """Return a singleton OpenSearch client."""
    global _os_client
    if _os_client is None:
        _os_client = OpenSearch(
            hosts=[config.OPENSEARCH_URL],
            http_auth=(config.OPENSEARCH_USER, config.OPENSEARCH_PASSWORD),
            use_ssl=config.OPENSEARCH_URL.startswith('https'),
            verify_certs=False,
            ssl_show_warn=False
        )
    return _os_client


def filter_logs(lines: List[str]) -> List[Dict]:
    """使用簡單關鍵字篩選可疑日誌行。

    此為漏斗的第一層防線，僅檢查行內是否包含 ``error`` 或 ``fail``，
    並將原始字串包裝成類似 Wazuh 回傳格式的 dict。
    """
    result = []
    for line in lines:
        if "error" in line.lower() or "fail" in line.lower():
            result.append({"line": line, "alert": {"original_log": line}})
    return result


def analyse_lines(lines: List[str]) -> List[Dict]:
    """執行多層過濾流程並回傳分析結果。

    參數
    ----
    lines:
        待處理的原始日誌行，可來自檔案或 HTTP 服務。

    回傳
    ----
    list[dict]
        通過所有過濾階段且已由語言模型分析之日誌行。
    """
    # 階段 0：透過關鍵字快速排除明顯無害的行
    candidates = filter_logs(lines)

    # 階段 1：如設定啟用，透過 Wazuh logtest 進一步比對規則
    if config.WAZUH_ENABLED:
        filtered: List[Dict] = []
        for entry in candidates:
            if wazuh_api.logtest(entry["line"]):
                filtered.append(entry)
        candidates = filtered

    if not candidates:
        return []

    # 階段 2：套用 ``log_parser`` 的啟發式規則計算分數
    scored = [(entry, fast_score(entry["line"])) for entry in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)

    top_n = max(1, int(len(scored) * config.SAMPLE_TOP_PERCENT / 100))
    selected = [e for e, _ in scored[:top_n]]

    # 階段 3：向量搜尋與圖譜查詢提供更多脈絡
    prompts = []
    for entry in selected:
        vec = embed(entry["line"])
        ids, _ = VECTOR_DB.search(vec, k=3)
        examples = [c.get("line") for c in VECTOR_DB.get_cases(ids)]
        graph = GRAPH_RETRIEVER.retrieve_for_line(entry["line"])
        prompts.append({"alert": entry.get("alert"), "examples": examples, "graph": graph})

    # 最後階段：將準備好的提示送入 LLM 進行深度分析
    analyses = llm_analyse(prompts) if prompts else []

    results: List[Dict] = []
    for entry, analysis in zip(selected, analyses):
        # Store new vectors along with the original entry so future searches
        # can surface them as examples
        vec = embed(entry["line"])
        VECTOR_DB.add([vec], [entry])
        entry["analysis"] = analysis
        if analysis.get("entities"):
            GRAPH_BUILDER.create_entities(analysis["entities"])
        if analysis.get("relations"):
            GRAPH_BUILDER.create_relations(analysis["relations"])
        results.append(entry)

    # Persist state and vector index so that context is preserved between runs
    save_state(STATE)
    VECTOR_DB.save()
    return results


def process_logs(paths: List[Path]) -> List[Dict]:
    """讀取檔案並呼叫 :func:`analyse_lines` 進行處理。

    此輔助函式主要供單元測試使用，避免在測試中啟動完整的 FastAPI；
    它僅將檔案內容逐行讀入後傳給 :func:`analyse_lines`。
    """
    lines: List[str] = []
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            lines.extend([l.rstrip("\n") for l in f])
    return analyse_lines(lines)


def process_new_logs(index: str = "filebeat-*") -> int:
    """Query OpenSearch for new logs and analyse them.

    Parameters
    ----------
    index:
        Index pattern to search for log documents.

    Returns
    -------
    int
        Number of documents processed.
    """
    client = _get_os_client()
    query = {
        "query": {
            "bool": {"must_not": {"term": {"ai_analysis_completed": True}}}
        }
    }
    resp = client.search(index=index, body=query, size=100)
    hits = resp.get("hits", {}).get("hits", [])
    for hit in hits:
        line = hit.get("_source", {}).get("message", "")
        if not line:
            continue
        results = analyse_lines([line])
        if not results:
            continue
        analysis = results[0].get("analysis", {})
        update_body = {
            "doc": {
                "analysis": analysis,
                "ai_analysis_completed": True,
            }
        }
        client.update(index=hit["_index"], id=hit["_id"], body=update_body)
    return len(hits)
