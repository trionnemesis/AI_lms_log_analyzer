"""Neo4j 實體與關係建立模組。

此模組負責解析 llm_analyse 回傳的 JSON，並
透過 py2neo 將事件相關實體與關聯寫入 Neo4j。
在單元測試或缺乏 Neo4j/py2neo 時會自動降級為無操作模式。"""

from __future__ import annotations

from typing import List, Dict

from .. import config
from .utils import logger

try:  # pragma: no cover - optional dependency
    from py2neo import Graph, Node, Relationship
except Exception:  # pragma: no cover - missing dependency
    Graph = None  # type: ignore
    Node = None  # type: ignore
    Relationship = None  # type: ignore


class GraphBuilder:
    """簡化的 Neo4j 連線與寫入封裝。"""

    def __init__(self, uri: str | None = None, user: str | None = None, password: str | None = None) -> None:
        self.uri = uri or config.NEO4J_URI
        self.user = user or config.NEO4J_USER
        self.password = password or config.NEO4J_PASSWORD
        self.graph = None
        if Graph is not None:
            try:
                self.graph = Graph(self.uri, auth=(self.user, self.password))
            except Exception as exc:  # pragma: no cover - connection errors
                logger.error("Neo4j connection failed: %s", exc)
                self.graph = None

    def create_entities(self, entities: List[Dict]) -> None:
        """建立或更新多個節點。"""
        if not self.graph or not Node:
            return
        tx = self.graph.begin()
        for ent in entities:
            label = ent.get("label", "Entity")
            node = Node(label, id=ent.get("id"), **(ent.get("properties") or {}))
            tx.merge(node, label, "id")
        tx.commit()

    def create_relations(self, relations: List[Dict]) -> None:
        """建立多個關係。"""
        if not self.graph or not Relationship:
            return
        tx = self.graph.begin()
        for rel in relations:
            start = self.graph.nodes.match(id=rel.get("start_id")).first()
            end = self.graph.nodes.match(id=rel.get("end_id")).first()
            if not start or not end:
                continue
            r = Relationship(start, rel.get("type", "RELATED"), end)
            tx.merge(r)
        tx.commit()
