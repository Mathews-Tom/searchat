"""In-memory BM25 index for palace objects."""
from __future__ import annotations

from typing import TYPE_CHECKING

from rank_bm25 import BM25Okapi

if TYPE_CHECKING:
    from searchat.palace.storage import PalaceStorage


class PalaceBM25Index:
    """In-memory BM25 index over palace objects for keyword search."""

    def __init__(self) -> None:
        self.corpus: list[list[str]] = []
        self.object_ids: list[str] = []
        self.bm25: BM25Okapi | None = None

    def build_from_storage(
        self,
        storage: PalaceStorage,
        include_files: bool = True,
        include_rooms: bool = True,
    ) -> int:
        """Load all objects and rooms, build searchable corpus.

        Returns number of objects indexed.
        """
        self.corpus = []
        self.object_ids = []

        objects = storage.get_all_objects()
        if not objects:
            self.bm25 = None
            return 0

        # Build object_id -> rooms mapping
        object_rooms: dict[str, list[tuple[str, str]]] = {}
        rooms = storage.get_all_rooms()
        room_map = {r.room_id: (r.room_key, r.room_label) for r in rooms}

        rows = storage.get_room_object_pairs()
        for obj_id, room_id in rows:
            if obj_id not in object_rooms:
                object_rooms[obj_id] = []
            if room_id in room_map:
                object_rooms[obj_id].append(room_map[room_id])

        for obj in objects:
            text_parts = [obj.exchange_core, obj.specific_context]

            if obj.conv_title:
                text_parts.append(obj.conv_title)

            if include_files:
                for ft in obj.files_touched:
                    text_parts.append(ft.path)

            if include_rooms:
                for room_key, room_label in object_rooms.get(obj.object_id, []):
                    text_parts.append(room_key)
                    text_parts.append(room_label)

            full_text = " ".join(text_parts)
            tokens = self._tokenize(full_text)

            self.corpus.append(tokens)
            self.object_ids.append(obj.object_id)

        if self.corpus:
            self.bm25 = BM25Okapi(self.corpus)

        return len(self.object_ids)

    def search(self, query: str, limit: int = 50) -> list[tuple[str, float]]:
        """Search index, return (object_id, score) pairs sorted by score descending."""
        if self.bm25 is None or not self.corpus:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scores = self.bm25.get_scores(query_tokens)

        scored = [
            (self.object_ids[i], float(scores[i]))
            for i in range(len(scores))
            if scores[i] > 0
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenization: lowercase and split on separators."""
        text = text.lower()
        for sep in ["_", "-", "/", "\\", ".", ":"]:
            text = text.replace(sep, " ")
        return text.split()

    @property
    def size(self) -> int:
        return len(self.object_ids)
