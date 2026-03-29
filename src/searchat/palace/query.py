"""Palace query engine for searching distilled conversation data."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

from searchat.config import Config
from searchat.models.domain import DistilledObject, PalaceSearchResult, Room
from searchat.palace.bm25_index import PalaceBM25Index
from searchat.palace.faiss_index import DistilledFaissIndex
from searchat.palace.storage import PalaceStorage

logger = logging.getLogger(__name__)


def _percentile_normalize(values: list[float], percentile: float = 95.0) -> float:
    """Return the percentile value for normalization, or 1.0 if empty."""
    if not values:
        return 1.0
    arr = np.array(values, dtype=np.float32)
    p = float(np.percentile(arr, percentile))
    return p if p > 0 else 1.0


def _normalize_score(score: float, divisor: float) -> float:
    """Normalize a score to 0-1 range using a divisor, capping at 1.0."""
    if divisor <= 0:
        return 0.0
    return min(score / divisor, 1.0)


class PalaceQuery:
    """Query interface for palace distilled data."""

    def __init__(
        self,
        data_dir: Path,
        config: Config,
        embedder: SentenceTransformer | None = None,
        palace_storage: PalaceStorage | None = None,
    ) -> None:
        self.data_dir = data_dir
        self.config = config
        self.storage = palace_storage if palace_storage is not None else PalaceStorage(data_dir)
        self.faiss_index = DistilledFaissIndex(data_dir / "indices", config)
        if embedder is not None:
            self.embedder = embedder
        else:
            from sentence_transformers import SentenceTransformer as ST
            self.embedder = ST(config.embedding.model, device=config.embedding.get_device())
        self.bm25_index = PalaceBM25Index()
        self._bm25_initialized = False
        self._bm25_change_token = -1

    def ensure_bm25_index(self) -> int:
        """Build BM25 index if not already initialized. Returns object count."""
        current_token = self.storage.get_change_token()
        if self._bm25_initialized and self._bm25_change_token == current_token:
            return self.bm25_index.size
        count = self.bm25_index.build_from_storage(self.storage)
        self._bm25_initialized = True
        self._bm25_change_token = current_token
        return count

    def walk_room(self, room_id: str) -> list[DistilledObject]:
        """Get all objects in a room, ordered chronologically."""
        return self.storage.get_objects_in_room(room_id)

    def find_rooms(self, query: str, limit: int = 20) -> list[Room]:
        """Find rooms by keyword + semantic search."""
        keyword_rooms = self.storage.find_rooms_by_keyword(query, limit=limit)
        keyword_room_ids = {r.room_id for r in keyword_rooms}

        query_embedding = self.embedder.encode(query)
        query_embedding = np.array(query_embedding, dtype=np.float32)
        distances, indices = self.faiss_index.search(query_embedding, k=50)

        if indices.size == 0 or (indices.size > 0 and indices[0][0] == -1):
            return keyword_rooms[:limit]

        valid_mask = indices[0] >= 0
        valid_indices = [int(idx) for idx in indices[0][valid_mask]]
        valid_distances = distances[0][valid_mask].tolist()
        if not valid_indices:
            return keyword_rooms[:limit]

        object_ids = self.faiss_index.get_object_ids_from_vectors(valid_indices)
        if not object_ids:
            return keyword_rooms[:limit]

        object_distances: dict[str, float] = {}
        vid_to_oid = self.faiss_index._vid_to_oid
        for vid, dist in zip(valid_indices, valid_distances):
            oid = vid_to_oid.get(vid)
            if oid is not None:
                object_distances[oid] = dist

        semantic_rooms = self._score_room_hits(object_ids, object_distances)

        result = list(keyword_rooms)
        for room in semantic_rooms:
            if room.room_id not in keyword_room_ids:
                result.append(room)
                keyword_room_ids.add(room.room_id)

        return result[:limit]

    def search_distilled(self, query: str, k: int = 50) -> list[DistilledObject]:
        """Semantic search over distilled objects."""
        query_embedding = self.embedder.encode(query)
        query_embedding = np.array(query_embedding, dtype=np.float32)
        distances, indices = self.faiss_index.search(query_embedding, k=k)

        if indices.size == 0 or (indices.size > 0 and indices[0][0] == -1):
            return []

        valid_indices = [int(idx) for idx in indices[0] if idx >= 0]
        if not valid_indices:
            return []

        object_ids = self.faiss_index.get_object_ids_from_vectors(valid_indices)
        return self.storage.get_objects_by_ids(object_ids)

    def search_hybrid(
        self,
        query: str,
        limit: int = 50,
        keyword_weight: float = 0.5,
        semantic_weight: float = 0.5,
        project_ids: list[str] | None = None,
    ) -> list[PalaceSearchResult]:
        """Hybrid search combining BM25 keyword and FAISS semantic."""
        self.ensure_bm25_index()

        # BM25 keyword search
        keyword_results = self.bm25_index.search(query, limit=limit * 2)
        keyword_scores: dict[str, float] = dict(keyword_results)

        # FAISS semantic search
        semantic_scores: dict[str, float] = {}
        query_embedding = self.embedder.encode(query)
        query_embedding = np.array(query_embedding, dtype=np.float32)
        distances, indices = self.faiss_index.search(query_embedding, k=limit * 2)

        if indices.size > 0 and indices[0][0] >= 0:
            valid_mask = indices[0] >= 0
            valid_indices = [int(idx) for idx in indices[0][valid_mask]]
            valid_distances = distances[0][valid_mask].tolist()

            vid_to_oid = self.faiss_index._vid_to_oid
            for vid, dist in zip(valid_indices, valid_distances):
                oid = vid_to_oid.get(vid)
                if oid is not None:
                    semantic_scores[oid] = 1.0 / (1.0 + dist)

        # Merge scores
        all_object_ids: set[str] = set(keyword_scores.keys()) | set(semantic_scores.keys())
        if not all_object_ids:
            return []

        kw_divisor = _percentile_normalize(list(keyword_scores.values()))
        sem_divisor = _percentile_normalize(list(semantic_scores.values()))

        combined: dict[str, tuple[float, float, float]] = {}
        for oid in all_object_ids:
            kw_score = _normalize_score(keyword_scores.get(oid, 0.0), kw_divisor)
            sem_score = _normalize_score(semantic_scores.get(oid, 0.0), sem_divisor)

            base_score = keyword_weight * kw_score + semantic_weight * sem_score
            if oid in keyword_scores and oid in semantic_scores:
                base_score *= 1.2  # intersection boost

            combined[oid] = (base_score, kw_score, sem_score)

        ranked = sorted(combined.items(), key=lambda x: x[1][0], reverse=True)[:limit]

        # Build results with metadata
        ranked_oids = [oid for oid, _ in ranked]
        objects_list = self.storage.get_objects_by_ids(ranked_oids)
        obj_map = {o.object_id: o for o in objects_list}

        pairs = self.storage.get_room_object_pairs(ranked_oids)
        oid_to_room_ids: dict[str, list[str]] = {}
        all_room_ids: set[str] = set()
        for obj_id, room_id in pairs:
            oid_to_room_ids.setdefault(obj_id, []).append(room_id)
            all_room_ids.add(room_id)
        rooms_list = self.storage.get_rooms_by_ids(list(all_room_ids))
        room_map = {r.room_id: r for r in rooms_list}

        project_set = set(project_ids) if project_ids else None
        results: list[PalaceSearchResult] = []
        for oid, (score, kw_score, sem_score) in ranked:
            obj = obj_map.get(oid)
            if obj is None:
                continue
            if project_set and obj.project_id not in project_set:
                continue

            rooms = [room_map[rid] for rid in oid_to_room_ids.get(oid, []) if rid in room_map]

            results.append(PalaceSearchResult(
                object_id=obj.object_id,
                conversation_id=obj.conversation_id,
                project_id=obj.project_id,
                ply_start=obj.ply_start,
                ply_end=obj.ply_end,
                exchange_core=obj.exchange_core,
                specific_context=obj.specific_context,
                files_touched=obj.files_touched,
                rooms=rooms,
                score=score,
                keyword_score=kw_score,
                semantic_score=sem_score,
            ))

        return results

    def _score_room_hits(
        self, object_ids: list[str], object_distances: dict[str, float],
    ) -> list[Room]:
        """Score rooms by mean semantic proximity of their objects."""
        if not object_ids:
            return []

        pairs = self.storage.get_room_object_pairs(object_ids)
        if not pairs:
            return []

        room_ids_needed: set[str] = set()
        obj_to_rooms: dict[str, list[str]] = {}
        for obj_id, room_id in pairs:
            room_ids_needed.add(room_id)
            obj_to_rooms.setdefault(obj_id, []).append(room_id)

        rooms_list = self.storage.get_rooms_by_ids(list(room_ids_needed))
        room_data: dict[str, Room] = {r.room_id: r for r in rooms_list}

        room_scores: dict[str, list[float]] = {}
        for obj_id, room_id_list in obj_to_rooms.items():
            dist = object_distances.get(obj_id, float("inf"))
            score = 1.0 / (1.0 + dist)
            for rid in room_id_list:
                room_scores.setdefault(rid, []).append(score)

        ranked = sorted(
            room_scores.items(),
            key=lambda item: sum(item[1]) / len(item[1]),
            reverse=True,
        )

        return [room_data[rid] for rid, _ in ranked if rid in room_data]

    def close(self) -> None:
        self.storage.close()
