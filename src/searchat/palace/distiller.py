"""Main distillation engine for the memory palace system."""
from __future__ import annotations

import hashlib
import logging
import re
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

from searchat.config import Config
from searchat.models.domain import (
    DistilledObject,
    DistillationStats,
    FileTouched,
    Room,
    RoomObject,
)
from searchat.palace.faiss_index import DistilledFaissIndex
from searchat.palace.llm import DistillationInput, DistillationLLM, RoomAssignment
from searchat.palace.storage import PalaceStorage

logger = logging.getLogger(__name__)

# Extensions recognized as file paths when matched by regex.
_FILE_EXTENSIONS = frozenset({
    "py", "js", "ts", "tsx", "jsx", "json", "jsonl", "toml", "yaml", "yml",
    "md", "html", "css", "scss", "sql", "sh", "bash", "zsh", "cfg", "ini",
    "txt", "xml", "csv", "parquet", "lock", "env", "dockerfile",
    "rs", "go", "java", "c", "h", "cpp", "hpp", "rb", "php", "swift",
    "kt", "scala", "ex", "exs", "erl", "hs", "ml", "r", "jl",
    "vue", "svelte", "astro", "prisma", "graphql", "proto", "tf",
    "conf", "log", "pid", "sock", "wasm", "map",
})

_PATH_PATTERN = re.compile(
    r'(?:[\w./\\~-]+[/\\])?'
    r'[\w.-]+'
    r'\.'
    r'(' + '|'.join(_FILE_EXTENSIONS) + r')'
    r'\b',
    re.IGNORECASE,
)

_BACKTICK_INLINE = re.compile(r'`([^`\n]+)`')


def extract_file_paths(text: str) -> list[str]:
    """Extract deduplicated file paths from text using regex."""
    seen: set[str] = set()
    result: list[str] = []

    def _add(path: str) -> None:
        normalized = path.replace("\\", "/")
        if normalized.startswith("./"):
            normalized = normalized[2:]
        if normalized not in seen:
            seen.add(normalized)
            result.append(normalized)

    for match in _BACKTICK_INLINE.finditer(text):
        content = match.group(1).strip()
        for path_match in _PATH_PATTERN.finditer(content):
            _add(path_match.group(0))

    for match in _PATH_PATTERN.finditer(text):
        _add(match.group(0))

    return result


def make_room_id(room_type: str, room_key: str, project_id: str | None = None) -> str:
    """Deterministic room ID from type + key + project."""
    key = f"{room_type}:{room_key}:{project_id or ''}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


class Distiller:
    """Distillation engine for converting conversations into structured palace objects."""

    def __init__(
        self,
        search_dir: Path,
        config: Config,
        llm: DistillationLLM | None = None,
        duckdb_store: object | None = None,
        embedder: SentenceTransformer | None = None,
        palace_storage: PalaceStorage | None = None,
        indexing_lock: threading.Lock | None = None,
    ) -> None:
        self.search_dir = search_dir
        self.config = config
        self.data_dir = search_dir / "data"
        self.storage = palace_storage if palace_storage is not None else PalaceStorage(self.data_dir)
        self.faiss_index = DistilledFaissIndex(self.data_dir / "indices", config)
        self.llm = llm
        self.duckdb_store = duckdb_store
        self._indexing_lock = indexing_lock or threading.Lock()
        self._distill_lock = threading.Lock()
        if embedder is not None:
            self.embedder = embedder
        else:
            from sentence_transformers import SentenceTransformer as ST
            self.embedder = ST(config.embedding.model, device=config.embedding.get_device())

    def distill_conversation(self, conversation_id: str) -> list[DistilledObject]:
        """Distill a single conversation using the LLM."""
        if self.llm is None:
            raise RuntimeError("No LLM configured for distillation.")

        conv = self._read_conversation(conversation_id)
        if conv is None:
            raise KeyError(f"Conversation not found: {conversation_id}")

        messages = conv["messages"]
        project_id = conv["project_id"]
        exchanges = self._segment_exchanges(messages)

        if not exchanges:
            self.storage.mark_conversation_skipped(conversation_id, "no_valid_exchanges")
            return []

        existing_keys = self.storage.get_existing_object_keys(conversation_id)
        inputs = []
        exchange_meta = []

        for ply_start, ply_end in exchanges:
            if (conversation_id, ply_start, ply_end) in existing_keys:
                continue
            exchange_msgs = [
                m for m in messages if ply_start <= m["sequence"] <= ply_end
            ]
            inputs.append(DistillationInput(
                conversation_id=conversation_id,
                project_id=project_id,
                messages=exchange_msgs,
                ply_start=ply_start,
                ply_end=ply_end,
            ))
            exchange_meta.append((ply_start, ply_end, exchange_msgs))

        if not inputs:
            return []

        outputs = self.llm.distill(inputs)

        objects = []
        rooms = []
        junctions = []
        now = datetime.utcnow()

        for i, output in enumerate(outputs):
            ply_start, ply_end, exchange_msgs = exchange_meta[i]

            exchange_at = now
            if exchange_msgs:
                ts = exchange_msgs[0].get("timestamp")
                if isinstance(ts, datetime):
                    exchange_at = ts
                elif isinstance(ts, str):
                    try:
                        exchange_at = datetime.fromisoformat(ts)
                    except (ValueError, TypeError):
                        pass

            combined_text = "\n".join(m.get("content", "") or "" for m in exchange_msgs)
            extracted_paths = extract_file_paths(combined_text)
            files_touched = [FileTouched(path=p, action="referenced") for p in extracted_paths]

            distilled_text = f"{output.exchange_core}\n{output.specific_context}"
            object_id = str(uuid.uuid4())

            obj = DistilledObject(
                object_id=object_id,
                project_id=project_id,
                conversation_id=conversation_id,
                ply_start=ply_start,
                ply_end=ply_end,
                files_touched=files_touched,
                exchange_core=output.exchange_core,
                specific_context=output.specific_context,
                created_at=now,
                exchange_at=exchange_at,
                embedding_id=-1,
                distilled_text=distilled_text,
            )
            objects.append(obj)

            for ra in output.room_assignments:
                room_id = make_room_id(ra.room_type, ra.room_key, project_id)
                room = Room(
                    room_id=room_id,
                    room_type=ra.room_type,
                    room_key=ra.room_key,
                    room_label=ra.room_label,
                    project_id=project_id,
                    created_at=now,
                    updated_at=now,
                    object_count=1,
                )
                rooms.append(room)
                junctions.append(RoomObject(
                    room_id=room_id,
                    object_id=object_id,
                    relevance=ra.relevance,
                    placed_at=now,
                ))

        self.flush(objects, rooms, junctions)
        return objects

    def distill_all_pending(self, project_id: str | None = None) -> DistillationStats:
        """Distill all conversations not yet fully distilled."""
        if not self._distill_lock.acquire(blocking=False):
            logger.info("Distillation already in progress, skipping")
            return DistillationStats(
                conversations_processed=0,
                objects_created=0,
                rooms_created=0,
                rooms_updated=0,
                distillation_time_seconds=0.0,
            )

        try:
            return self._distill_all_pending_locked(project_id)
        finally:
            self._distill_lock.release()

    def _distill_all_pending_locked(self, project_id: str | None = None) -> DistillationStats:
        start = time.time()
        conversation_ids = self.list_pending_conversations(project_id)

        total_objects = 0
        conversations_processed = 0

        for conv_id in conversation_ids:
            try:
                new_objects = self.distill_conversation(conv_id)
                total_objects += len(new_objects)
                conversations_processed += 1
            except (KeyError, ValueError, AttributeError) as e:
                logger.warning("Failed to distill conversation %s: %s", conv_id, e)
                self.storage.mark_conversation_skipped(conv_id, f"llm_error: {e}")
                continue
            except RuntimeError as e:
                logger.warning("Failed to distill conversation %s (will retry): %s", conv_id, e)
                continue

        elapsed = time.time() - start
        return DistillationStats(
            conversations_processed=conversations_processed,
            objects_created=total_objects,
            rooms_created=0,
            rooms_updated=0,
            distillation_time_seconds=elapsed,
        )

    def flush(
        self,
        objects: list[DistilledObject],
        rooms: list[Room],
        junctions: list[RoomObject],
    ) -> None:
        """Embed objects, assign vector IDs, write to DuckDB + FAISS."""
        if not objects:
            return

        texts = [obj.distilled_text for obj in objects]
        embeddings = self.embedder.encode(texts, batch_size=self.config.embedding.batch_size)
        embeddings = np.array(embeddings, dtype=np.float32)

        vector_ids = self.faiss_index.append_vectors(
            object_ids=[obj.object_id for obj in objects],
            project_ids=[obj.project_id for obj in objects],
            distilled_texts=texts,
            embeddings=embeddings,
            created_at_values=[obj.created_at for obj in objects],
        )

        for i, obj in enumerate(objects):
            obj.embedding_id = vector_ids[i]

        self.storage.store_distillation_results(objects, rooms, junctions)

    def _segment_exchanges(self, messages: list[dict]) -> list[tuple[int, int]]:
        """Segment messages into exchanges, dropping empty ones at source."""
        if not messages:
            return []

        sorted_msgs = sorted(messages, key=lambda m: m.get("sequence", 0))
        content_by_seq = {
            m.get("sequence", 0): len(m.get("content", "") or "")
            for m in sorted_msgs
        }
        role_by_seq = {
            m.get("sequence", 0): m.get("role", "")
            for m in sorted_msgs
        }

        exchanges: list[tuple[int, int]] = []
        current_start: int | None = None
        current_end: int | None = None
        has_assistant_content = False

        for msg in sorted_msgs:
            seq = msg.get("sequence", 0)
            role = msg.get("role", "")
            content_len = content_by_seq.get(seq, 0)

            if role == "user":
                if current_start is not None and has_assistant_content:
                    exchanges.append((current_start, current_end))  # type: ignore[arg-type]
                    current_start = seq
                    current_end = seq
                    has_assistant_content = False
                elif current_start is None:
                    current_start = seq
                    current_end = seq
                else:
                    current_end = seq
            else:
                if current_start is None:
                    current_start = seq
                current_end = seq
                if content_len > 0:
                    has_assistant_content = True

        if current_start is not None:
            exchanges.append((current_start, current_end))  # type: ignore[arg-type]

        # Drop empty exchanges
        min_chars = self.config.distillation.min_exchange_chars
        non_empty = []
        for start, end in exchanges:
            total_chars = sum(
                content_by_seq.get(seq, 0) for seq in range(start, end + 1)
            )
            user_chars = sum(
                content_by_seq.get(seq, 0)
                for seq in range(start, end + 1)
                if role_by_seq.get(seq) == "user"
            )
            if total_chars < min_chars:
                continue
            if user_chars == 0:
                continue
            non_empty.append((start, end))

        # Enforce max_ply_length
        max_ply = self.config.distillation.max_ply_length
        bounded = []
        for start, end in non_empty:
            if end - start + 1 > max_ply:
                for chunk_start in range(start, end + 1, max_ply):
                    chunk_end = min(chunk_start + max_ply - 1, end)
                    bounded.append((chunk_start, chunk_end))
            else:
                bounded.append((start, end))

        return bounded

    def _read_conversation(self, conversation_id: str) -> dict | None:
        """Read a conversation from storage."""
        if self.duckdb_store is None:
            raise RuntimeError(
                "duckdb_store is required for _read_conversation. "
                "Pass duckdb_store to Distiller constructor."
            )

        store = self.duckdb_store
        get_conv = getattr(store, "get_conversation", None)
        if get_conv is None:
            raise RuntimeError("duckdb_store must implement get_conversation()")

        conv = get_conv(conversation_id)
        if conv is None:
            return None

        get_msgs = getattr(store, "get_conversation_messages", None)
        if get_msgs is None:
            raise RuntimeError("duckdb_store must implement get_conversation_messages()")

        messages = get_msgs(conversation_id)

        return {
            "conversation_id": conv["conversation_id"],
            "project_id": conv["project_id"],
            "messages": messages,
        }

    def list_pending_conversations(self, project_id: str | None = None) -> list[str]:
        """List conversation IDs that have undistilled exchanges."""
        if self.duckdb_store is None:
            raise RuntimeError(
                "duckdb_store is required for list_pending_conversations."
            )

        get_all_ids = getattr(self.duckdb_store, "get_all_conversation_ids", None)
        if get_all_ids is None:
            raise RuntimeError("duckdb_store must implement get_all_conversation_ids()")

        all_ids = set(get_all_ids(project_id))
        distilled_ids = self.storage.get_distilled_conversation_ids()
        skipped_ids = self.storage.get_skipped_conversation_ids()

        return sorted(all_ids - distilled_ids - skipped_ids)

    def close(self) -> None:
        self.storage.close()
