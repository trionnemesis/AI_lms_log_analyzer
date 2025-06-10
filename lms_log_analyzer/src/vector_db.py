"""超輕量化的向量資料庫，僅供單元測試使用。

正式環境應會以 FAISS 等高效方案實作，此處僅將向量與案例
簡單寫入 JSON 方便測試流程運行。
"""

import json
from pathlib import Path
from typing import Iterable, List, Dict, Tuple

from .. import config


def _l2(vec1: List[float], vec2: List[float]) -> float:
    """計算兩向量的歐氏距離。"""
    return sum((a - b) ** 2 for a, b in zip(vec1, vec2)) ** 0.5


def embed(text: str) -> List[float]:
    """以字元編碼簡單產生向量。"""
    base = sum(ord(c) for c in text)
    return [float(base % 1000)]


class SimpleVectorDB:
    """記憶體中的向量儲存，並可選擇寫入 JSON 持久化。"""

    def __init__(self, path: Path | None = None):
        """若路徑存在即讀取既有索引。"""
        self.path = Path(path or config.VECTOR_DB_PATH)
        self.vectors: List[List[float]] = []
        self.cases: List[Dict] = []
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                self.vectors = data.get("vectors", [])
                self.cases = data.get("cases", [])
            except Exception:
                # 若檔案損毀則重新建立空白資料庫
                self.vectors = []
                self.cases = []

    def add(self, vecs: List[List[float]], cases: List[Dict]) -> None:
        """新增向量及其案例。"""
        self.vectors.extend(vecs)
        self.cases.extend(cases)

    def search(self, vec: List[float], k: int = 3) -> Tuple[List[int], List[float]]:
        """搜尋 ``k`` 個最近向量並回傳其索引與距離。"""
        if not self.vectors:
            return [], []
        dists = [_l2(v, vec) for v in self.vectors]
        sorted_ids = sorted(range(len(dists)), key=lambda i: dists[i])[:k]
        return sorted_ids, [dists[i] for i in sorted_ids]

    def get_cases(self, ids: Iterable[int]) -> List[Dict]:
        """依向量索引取得儲存的案例。"""
        return [self.cases[i] for i in ids if 0 <= i < len(self.cases)]

    def save(self) -> None:
        """將向量與案例寫入磁碟。"""
        try:
            data = {"vectors": self.vectors, "cases": self.cases}
            self.path.write_text(json.dumps(data))
        except Exception:
            # 測試環境若寫入失敗則直接忽略
            pass


VECTOR_DB = SimpleVectorDB()
