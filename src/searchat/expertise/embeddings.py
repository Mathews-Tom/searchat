"""FAISS-based embedding index for expertise records."""
from __future__ import annotations

import logging
from pathlib import Path
from threading import Lock
from collections.abc import Callable
from typing import TYPE_CHECKING

import faiss
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from searchat.expertise.models import ExpertiseRecord

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

_EMBEDDING_DIM = 384
_logger = logging.getLogger(__name__)


class ExpertiseEmbeddingIndex:
    def __init__(self, data_dir: Path, embedding_model: str = "all-MiniLM-L6-v2") -> None:
        self._data_dir = data_dir
        self._embedding_model = embedding_model
        self._expertise_dir = data_dir / "expertise"
        self._faiss_path = self._expertise_dir / "expertise_embeddings.faiss"
        self._metadata_path = self._expertise_dir / "expertise_embeddings.metadata.parquet"

        self._lock = Lock()
        self._embedder: SentenceTransformer | None = None
        self._index: faiss.Index | None = None
        # Maps record_id (str) -> vector_id (int)
        self._record_to_vec: dict[str, int] = {}
        # Maps vector_id (int) -> record_id (str)
        self._vec_to_record: dict[int, str] = {}
        self._next_id: int = 0

        self._load_or_create()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, record: ExpertiseRecord) -> None:
        with self._lock:
            self._ensure_embedder()
            vec = self._embed(record.content)
            self._add_vector(record.id, vec)
            self._save()

    def add_batch(self, records: list[ExpertiseRecord]) -> None:
        if not records:
            return
        with self._lock:
            self._ensure_embedder()
            texts = [r.content for r in records]
            vecs = self._embed_batch(texts)
            for record, vec in zip(records, vecs):
                self._add_vector(record.id, vec)
            self._save()

    def search(self, query: str, limit: int = 5, min_similarity: float = 0.0) -> list[tuple[str, float]]:
        with self._lock:
            assert self._index is not None
            if self._index.ntotal == 0:
                return []
            self._ensure_embedder()
            vec = self._embed(query)
            k = min(limit, self._index.ntotal)
            scores, ids = self._index.search(vec, k)
            results: list[tuple[str, float]] = []
            for score, vid in zip(scores[0], ids[0]):
                if vid == -1:
                    continue
                if score < min_similarity:
                    continue
                record_id = self._vec_to_record.get(int(vid))
                if record_id is not None:
                    results.append((record_id, float(score)))
            return results

    def find_similar(self, content: str, limit: int = 3) -> list[tuple[str, float]]:
        return self.search(content, limit=limit)

    def remove(self, record_id: str) -> None:
        with self._lock:
            assert self._index is not None
            vec_id = self._record_to_vec.get(record_id)
            if vec_id is None:
                return
            id_selector = faiss.IDSelectorArray(np.array([vec_id], dtype=np.int64))
            self._index.remove_ids(id_selector)
            del self._record_to_vec[record_id]
            del self._vec_to_record[vec_id]
            self._save()

    def rebuild(
        self,
        records: list[ExpertiseRecord],
        progress_callback: Callable[[int, int], None] | None = None,
        batch_size: int = 100,
    ) -> None:
        with self._lock:
            self._index = self._create_index()
            self._record_to_vec = {}
            self._vec_to_record = {}
            self._next_id = 0
            if records:
                self._ensure_embedder()
                total = len(records)
                for start in range(0, total, batch_size):
                    chunk = records[start : start + batch_size]
                    texts = [r.content for r in chunk]
                    vecs = self._embed_batch(texts)
                    for record, vec in zip(chunk, vecs):
                        self._add_vector(record.id, vec)
                    if progress_callback is not None:
                        progress_callback(min(start + batch_size, total), total)
            self._save()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_or_create(self) -> None:
        self._expertise_dir.mkdir(parents=True, exist_ok=True)
        if self._faiss_path.exists() and self._metadata_path.exists():
            self._index = faiss.read_index(str(self._faiss_path))
            table = pq.read_table(self._metadata_path)
            vector_ids = table.column("vector_id").to_pylist()
            record_ids = table.column("record_id").to_pylist()
            for vid, rid in zip(vector_ids, record_ids):
                self._record_to_vec[rid] = int(vid)
                self._vec_to_record[int(vid)] = rid
            self._next_id = max(vector_ids, default=-1) + 1
        else:
            self._index = self._create_index()

    def _save(self) -> None:
        assert self._index is not None
        self._expertise_dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(self._faiss_path))
        table = pa.table(
            {
                "vector_id": pa.array(list(self._vec_to_record.keys()), type=pa.int64()),
                "record_id": pa.array(list(self._vec_to_record.values()), type=pa.string()),
            }
        )
        pq.write_table(table, self._metadata_path)

    def _create_index(self) -> faiss.Index:
        flat = faiss.IndexFlatIP(_EMBEDDING_DIM)
        return faiss.IndexIDMap2(flat)

    def _add_vector(self, record_id: str, vec: np.ndarray) -> None:
        assert self._index is not None
        vid = self._next_id
        self._next_id += 1
        ids = np.array([vid], dtype=np.int64)
        self._index.add_with_ids(vec.reshape(1, -1), ids)
        self._record_to_vec[record_id] = vid
        self._vec_to_record[vid] = record_id

    def _ensure_embedder(self) -> None:
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer

            self._embedder = SentenceTransformer(self._embedding_model)

    def _embed(self, text: str) -> np.ndarray:
        assert self._embedder is not None
        vec = self._embedder.encode([text], convert_to_numpy=True, normalize_embeddings=True)
        return vec.astype(np.float32)

    def _embed_batch(self, texts: list[str]) -> np.ndarray:
        assert self._embedder is not None
        vecs = self._embedder.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        return vecs.astype(np.float32)
