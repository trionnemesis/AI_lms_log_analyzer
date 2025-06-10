"""Neo4j 子圖查詢工具 (GraphRetrievalTool)。

此模組提供在 LangChain Agent 中使用的圖譜查詢功能，
輸入可疑日誌行後會解析其中的實體 ID，
並向 Neo4j 取得與其相關的節點與關係作為額外脈絡。
在缺乏 Neo4j 或 py2neo 的環境下會自動降級為 no-op。
"""

from __future__ import annotations

from typing import List, Dict

from .graph_builder import GraphBuilder
from .llm_handler import _extract_entities


class GraphRetrievalTool:
    """提供從 Neo4j 擷取子圖的能力。"""

    def __init__(self, builder: GraphBuilder | None = None) -> None:
        self.builder = builder or GraphBuilder()
        self.graph = self.builder.graph

    def retrieve_for_line(self, line: str, depth: int = 1) -> Dict[str, List[Dict]]:
        """依日誌行取得相關子圖。"""
        if not self.graph:
            return {"nodes": [], "relationships": []}
        entities = _extract_entities(line)
        nodes: List[Dict] = []
        relations: List[Dict] = []
        for ent in entities:
            sub = self._query_subgraph(ent.get("id"), depth)
            nodes.extend(sub["nodes"])
            relations.extend(sub["relationships"])
        return {"nodes": nodes, "relationships": relations}

    def _query_subgraph(self, entity_id: str, depth: int) -> Dict[str, List[Dict]]:
        if not self.graph:
            return {"nodes": [], "relationships": []}
        cypher = (
            f"MATCH p=(n {{id:$eid}})-[*1..{depth}]-(m) "
            "RETURN nodes(p) as nodes, relationships(p) as rels"
        )
        result = self.graph.run(cypher, eid=entity_id)
        nodes: List[Dict] = []
        rels: List[Dict] = []
        for row in result:
            for n in row.get("nodes", []):
                nodes.append({
                    "id": n.get("id"),
                    "labels": list(getattr(n, "labels", [])),
                    "properties": dict(n),
                })
            for r in row.get("rels", []):
                rels.append({
                    "start_id": r.start_node.get("id"),
                    "end_id": r.end_node.get("id"),
                    "type": type(r).__name__,
                })
        return {"nodes": nodes, "relationships": rels}
