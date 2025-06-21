"""FAISS 向量資料庫與 SentenceTransformer 嵌入。

此模組提供基本的向量化與搜尋能力，將案例寫入 JSON，索引則使用
FAISS 儲存。與先前僅存檔 JSON 的實作相比，能在大量資料下提供
更快速的相似度查詢。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Dict, Tuple

import numpy as np

try:
    import faiss  # type: ignore
except Exception:  # pragma: no cover - fallback for environments without faiss
    class _FallbackIndex:
        """Simplified FAISS-like index using NumPy."""

        def __init__(self, dim: int):
            self.vecs = np.empty((0, dim), dtype="float32")

        @property
        def ntotal(self) -> int:
            return len(self.vecs)

        def add(self, arr: np.ndarray) -> None:
            self.vecs = np.vstack([self.vecs, arr])

        def search(self, arr: np.ndarray, k: int) -> Tuple[np.ndarray, np.ndarray]:
            if self.ntotal == 0:
                dists = np.zeros((arr.shape[0], k), dtype="float32")
                ids = -np.ones((arr.shape[0], k), dtype=int)
                return dists, ids
            diffs = self.vecs[None, :, :] - arr[:, None, :]
            dists = (diffs ** 2).sum(axis=2)
            idx = np.argsort(dists, axis=1)[:, :k]
            sorted_dists = np.take_along_axis(dists, idx, axis=1)
            return sorted_dists.astype("float32"), idx

    class _FakeFaiss:
        IndexFlatL2 = _FallbackIndex

        @staticmethod
        def read_index(path: str) -> _FallbackIndex:
            return _FallbackIndex(0)

        @staticmethod
        def write_index(index: _FallbackIndex, path: str) -> None:
            pass

    faiss = _FakeFaiss()

from .. import config


_EMBEDDER: "SentenceTransformer" | None = None


def _get_embedder() -> "SentenceTransformer":
    """Lazily load the sentence embedding model."""
    global _EMBEDDER
    if _EMBEDDER is None:
        from sentence_transformers import SentenceTransformer
        _EMBEDDER = SentenceTransformer(config.EMBED_MODEL_NAME)
    return _EMBEDDER


def embed(text: str) -> List[float]:
    """產生 SentenceTransformer 向量。"""
    model = _get_embedder()
    vec = model.encode([text], convert_to_numpy=True)[0]
    return vec.astype("float32").tolist()


class SimpleVectorDB:
    """封裝 FAISS index 與案例 JSON。"""

    def __init__(self, path: Path | None = None, case_path: Path | None = None):
        """初始化資料庫並載入既有索引與案例。"""
        self.path = Path(path or config.VECTOR_DB_PATH)
        self.case_path = Path(case_path or config.CASE_DB_PATH)
        self.index: faiss.IndexFlatL2 | None = None
        if self.path.exists():
            try:
                self.index = faiss.read_index(str(self.path))
            except Exception:
                self.index = None

        self.cases: List[Dict] = []
        if self.case_path.exists():
            try:
                self.cases = json.loads(self.case_path.read_text())
            except Exception:
                self.cases = []

    def _ensure_index(self, dim: int) -> None:
        if self.index is None:
            self.index = faiss.IndexFlatL2(dim)

    def add(self, vecs: List[List[float]], cases: List[Dict]) -> None:
        """新增向量及案例。"""
        if not vecs:
            return
        arr = np.array(vecs, dtype="float32")
        self._ensure_index(arr.shape[1])
        self.index.add(arr)
        self.cases.extend(cases)

    def search(self, vec: List[float], k: int = 3) -> Tuple[List[int], List[float]]:
        """搜尋 ``k`` 個最近向量並回傳索引與距離。"""
        if self.index is None or self.index.ntotal == 0:
            return [], []
        arr = np.array([vec], dtype="float32")
        dists, ids = self.index.search(arr, k)
        return ids[0].tolist(), dists[0].tolist()

    def get_cases(self, ids: Iterable[int]) -> List[Dict]:
        """依向量索引取得案例。"""
        return [self.cases[i] for i in ids if 0 <= i < len(self.cases)]

    def save(self) -> None:
        """將索引與案例寫入磁碟。"""
        try:
            faiss.write_index(self.index, str(self.path))
            self.case_path.write_text(json.dumps(self.cases))
        except Exception:
            # 測試環境寫入失敗可忽略
            pass


VECTOR_DB = SimpleVectorDB()
