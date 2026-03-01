from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path
from dataclasses import asdict
import numpy as np
import faiss
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from searchat.core.logging_config import get_logger
from searchat.core.progress import ProgressCallback, NullProgressAdapter
from searchat.models import (
    ConversationRecord,
    MessageRecord,
    IndexStats,
    UpdateStats,
    CONVERSATION_SCHEMA,
    METADATA_SCHEMA,
    FILE_STATE_SCHEMA,
    CODE_BLOCK_SCHEMA,
)
from searchat.config import Config, PathResolver
from searchat.config.constants import (
    INDEX_SCHEMA_VERSION,
    INDEX_FORMAT_VERSION,
    INDEX_FORMAT,
    INDEX_METADATA_FILENAME,
)
from searchat.core.connectors import discover_all_files, detect_connector

logger = get_logger(__name__)


def _build_id_selector(ids: np.ndarray) -> faiss.IDSelector:
    try:
        return faiss.IDSelectorBatch(ids)  # type: ignore[call-arg]
    except Exception:
        return faiss.IDSelectorBatch(ids.size, faiss.swig_ptr(ids))  # type: ignore[call-arg]


class ConversationIndexer:
    """
    Indexes conversations from multiple AI coding agents.

    Supported agents:
    - Claude Code: ~/.claude/projects/**/*.jsonl
    - Mistral Vibe: ~/.vibe/logs/session/*.json
    - OpenCode: ~/.local/share/opencode/storage/session/*/*.json
    """

    def __init__(self, search_dir: Path, config: Config | None = None):
        self.search_dir = search_dir
        self.data_dir = search_dir / "data"
        self.conversations_dir = self.data_dir / "conversations"
        self.indices_dir = self.data_dir / "indices"
        self.code_dir = self.data_dir / "code"
        self.indexed_paths_path = self.indices_dir / "indexed_paths.parquet"
        self.file_state_path = self.indices_dir / "file_state.parquet"

        if config is None:
            config = Config.load()
        self.config = config

        # Embedder is initialized lazily (first indexing operation).
        self._embedder = None

        self.batch_size = config.embedding.batch_size
        self.chunk_size = 1500
        self.chunk_overlap = 200

        self._ensure_directories()

    def _write_indexed_paths(self, paths: set[str]) -> None:
        """Persist the set of indexed source file paths.

        This avoids scanning all conversation parquets on every watcher start.
        """
        table = pa.Table.from_pydict({"file_path": sorted(paths)})
        pq.write_table(table, self.indexed_paths_path)

    def _load_file_state(self) -> dict[str, dict]:
        if not self.file_state_path.exists():
            return {}
        table = pq.read_table(self.file_state_path)
        state: dict[str, dict] = {}
        for row in table.to_pylist():
            file_path = row.get("file_path")
            if isinstance(file_path, str):
                state[file_path] = row
        return state

    def _write_file_state(self, entries: list[dict]) -> None:
        table = pa.Table.from_pylist(entries, schema=FILE_STATE_SCHEMA)
        pq.write_table(table, self.file_state_path)

    def _backfill_file_state(self) -> dict[str, dict]:
        state: dict[str, dict] = {}
        for parquet_file in self.conversations_dir.glob("*.parquet"):
            table = pq.read_table(
                parquet_file,
                columns=["file_path", "file_hash", "indexed_at", "conversation_id", "project_id"],
            )
            for row in table.to_pylist():
                file_path = row.get("file_path")
                if not isinstance(file_path, str):
                    continue
                file_size = 0
                path_obj = Path(file_path)
                if path_obj.exists():
                    file_size = path_obj.stat().st_size
                connector_name = "unknown"
                try:
                    connector_name = detect_connector(path_obj).name
                except Exception:
                    connector_name = "unknown"
                state[file_path] = {
                    "file_path": file_path,
                    "file_hash": row.get("file_hash"),
                    "file_size": file_size,
                    "indexed_at": row.get("indexed_at"),
                    "connector_name": connector_name,
                    "conversation_id": row.get("conversation_id"),
                    "project_id": row.get("project_id"),
                }
        return state

    def _get_embedder(self):
        """Create and cache the embedding model on first use."""
        if self._embedder is not None:
            return self._embedder

        # Check for GPU availability and warn if not using it
        from searchat.gpu_check import check_and_warn_gpu

        check_and_warn_gpu()

        from sentence_transformers import SentenceTransformer

        device = self.config.embedding.get_device()
        logger.info(f"Initializing embedding model on device: {device}")
        self._embedder = SentenceTransformer(self.config.embedding.model, device=device)
        return self._embedder
    
    def _ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.conversations_dir.mkdir(exist_ok=True)
        self.indices_dir.mkdir(exist_ok=True)
        self.code_dir.mkdir(exist_ok=True)
    
    def _chunk_text(self, text: str, chunk_size: int | None = None, overlap: int | None = None) -> list[str]:
        if chunk_size is None:
            chunk_size = self.chunk_size
        if overlap is None:
            overlap = self.chunk_overlap
        
        if len(text) <= chunk_size:
            return [text]

        # Fast path for long unstructured text (no sentence boundaries): fixed-size chunks.
        if not re.search(r"[.!?]", text):
            overlap = max(0, min(overlap, chunk_size - 1))
            chunks: list[str] = []
            start = 0
            while start < len(text):
                end = min(start + chunk_size, len(text))
                chunks.append(text[start:end])
                if end >= len(text):
                    break
                start = max(0, end - overlap)
            return chunks
        
        # Split by sentences (simple approach using common punctuation)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        chunks = []
        current_chunk = []
        current_size = 0
        
        for sentence in sentences:
            sentence_size = len(sentence)
            
            # If single sentence exceeds chunk size, split it
            if sentence_size > chunk_size:
                # Add current chunk if it exists
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                    current_chunk = []
                    current_size = 0
                
                # Split long sentence by words
                words = sentence.split()
                temp_chunk = []
                temp_size = 0
                
                for word in words:
                    word_size = len(word) + 1  # +1 for space
                    if temp_size + word_size > chunk_size and temp_chunk:
                        chunks.append(' '.join(temp_chunk))
                        temp_chunk = [word]
                        temp_size = word_size
                    else:
                        temp_chunk.append(word)
                        temp_size += word_size
                
                if temp_chunk:
                    chunks.append(' '.join(temp_chunk))
            
            # If adding sentence exceeds chunk size, start new chunk
            elif current_size + sentence_size + 1 > chunk_size and current_chunk:
                chunks.append(' '.join(current_chunk))
                # Keep last sentences for overlap
                overlap_text = ' '.join(current_chunk[-2:]) if len(current_chunk) > 1 else ''
                current_chunk = [overlap_text, sentence] if overlap_text and overlap > 0 else [sentence]
                current_size = len(overlap_text) + sentence_size + 1 if overlap_text else sentence_size
            else:
                current_chunk.append(sentence)
                current_size += sentence_size + 1
        
        # Add remaining chunk
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks
    
    def _chunk_by_messages(self, messages: list[MessageRecord], title: str) -> list[dict]:
        chunks_with_metadata = []
        current_chunk = f"{title}\n\n"
        current_messages = []
        start_message_idx = 0
        
        for idx, msg in enumerate(messages):
            msg_text = f"{msg.content}\n\n"
            
            if len(current_chunk) + len(msg_text) > self.chunk_size and current_messages:
                chunks_with_metadata.append({
                    'text': current_chunk,
                    'start_message_index': start_message_idx,
                    'end_message_index': current_messages[-1]
                })
                
                overlap_size = 0
                overlap_messages = []
                for msg_idx in reversed(current_messages):
                    overlap_msg = messages[msg_idx]
                    overlap_text = f"{overlap_msg.role}: {overlap_msg.content}\n\n"
                    if overlap_size + len(overlap_text) <= self.chunk_overlap:
                        overlap_messages.insert(0, msg_idx)
                        overlap_size += len(overlap_text)
                    else:
                        break
                
                if overlap_messages:
                    current_chunk = ""
                    for msg_idx in overlap_messages:
                        overlap_msg = messages[msg_idx]
                        current_chunk += f"{overlap_msg.role}: {overlap_msg.content}\n\n"
                    start_message_idx = overlap_messages[0]
                    current_messages = overlap_messages.copy()
                else:
                    current_chunk = ""
                    current_messages = []
                    start_message_idx = idx
            
            current_chunk += msg_text
            current_messages.append(idx)
        
        if current_chunk.strip():
            chunks_with_metadata.append({
                'text': current_chunk,
                'start_message_index': start_message_idx,
                'end_message_index': current_messages[-1] if current_messages else 0
            })
        
        return chunks_with_metadata
    
    def index_all(
        self,
        force: bool = False,
        progress: ProgressCallback | None = None,
    ) -> IndexStats:
        """
        Build index from scratch by scanning all supported source files.

        SAFETY: If an existing index is detected, this requires force=True
        to prevent accidental data loss. The existing index will be completely
        replaced with data from current source files.

        Args:
            force: Must be True to rebuild when existing index is present.
                   This acknowledges that existing indexed data will be lost
                   if source JSONLs are missing or incomplete.
            progress: Optional progress callback for reporting

        Returns:
            IndexStats with indexing results

        Raises:
            RuntimeError: If existing index found and force=False
        """
        if progress is None:
            progress = NullProgressAdapter()
        if not self.config.indexing.enable_connectors:
            raise RuntimeError(
                "Connector loading is disabled. Set indexing.enable_connectors to true."
            )
        has_existing_index = self._has_existing_index()

        if has_existing_index and not force:
            raise RuntimeError(
                "Existing index detected. Full rebuild will REPLACE all indexed data.\n\n"
                "If source JSONLs are missing or incomplete, you will lose conversations.\n\n"
                "Options:\n"
                "  1. Use index_append_only() to safely add new conversations\n"
                "  2. Call index_all(force=True) if you have complete source files\n"
                "  3. Delete index manually: rm -rf <search_dir>/data/\n\n"
                f"Index location: {self.data_dir}"
            )

        if has_existing_index:
            logger.warning(
                f"Force rebuilding index. Existing data at {self.data_dir} will be replaced."
            )
            # Clear existing data
            import shutil
            if self.conversations_dir.exists():
                shutil.rmtree(self.conversations_dir)
            if self.indices_dir.exists():
                shutil.rmtree(self.indices_dir)
            self._ensure_directories()

        start_time = time.time()

        # Phase 1: Discovery
        progress.update_phase("Discovering conversation files")

        # Collect all files first for accurate progress tracking
        file_matches = discover_all_files(self.config)

        # Phase 2: Processing conversations
        progress.update_phase("Processing conversations")

        all_records: list[ConversationRecord] = []
        all_chunks_with_meta: list[dict] = []
        project_records_map: dict[str, list[ConversationRecord]] = {}
        file_state_entries: list[dict] = []
        connector_name_by_file_path: dict[str, str] = {}

        for idx, match in enumerate(file_matches, 1):
            json_file = match.path
            connector = match.connector
            display_name = f"{connector.name} | {json_file.name}"
            progress.update_file_progress(idx, len(file_matches), display_name)

            try:
                # Process based on agent type
                record = connector.parse(json_file, 0)

                # Skip conversations with no messages
                if record.message_count == 0:
                    continue

                all_records.append(record)

                connector_name_by_file_path[record.file_path] = connector.name

                project_key = record.project_id
                if project_key not in project_records_map:
                    project_records_map[project_key] = []
                project_records_map[project_key].append(record)

                file_size = json_file.stat().st_size if json_file.exists() else 0
                file_state_entries.append({
                    "file_path": record.file_path,
                    "file_hash": record.file_hash,
                    "file_size": file_size,
                    "indexed_at": record.indexed_at,
                    "connector_name": connector.name,
                    "conversation_id": record.conversation_id,
                    "project_id": record.project_id,
                })

                # Collect chunks (will batch encode later)
                chunks_with_meta = self._chunk_by_messages(record.messages, record.title)
                for chunk_idx, chunk in enumerate(chunks_with_meta):
                    chunk["_record"] = record
                    chunk["_chunk_index"] = chunk_idx
                    all_chunks_with_meta.append(chunk)

            except Exception as e:
                if connector.name == "claude":
                    raise RuntimeError(f"Failed to process {json_file}: {e}") from e
                logger.warning(f"Failed to process {connector.name} session {json_file}: {e}")
                continue

        # Phase 3: Generate embeddings
        progress.update_phase("Generating embeddings")
        embeddings_array = self._batch_encode_chunks(all_chunks_with_meta, progress)

        # Build metadata for FAISS index
        metadata: list[dict] = []
        vector_ids: list[int] = []
        next_vector_id = 0
        record_first_vector_id: dict[str, int] = {}
        for chunk_meta, _embedding in zip(all_chunks_with_meta, embeddings_array):
            record = chunk_meta["_record"]
            if record.conversation_id not in record_first_vector_id:
                record_first_vector_id[record.conversation_id] = next_vector_id
            vector_id = next_vector_id
            next_vector_id += 1
            vector_ids.append(vector_id)
            metadata.append({
                "vector_id": vector_id,
                "conversation_id": record.conversation_id,
                "project_id": record.project_id,
                "chunk_index": chunk_meta["_chunk_index"],
                "chunk_text": chunk_meta["text"],
                "message_start_index": chunk_meta["start_message_index"],
                "message_end_index": chunk_meta["end_message_index"],
                "created_at": record.created_at,
            })

        # Phase 4: Building index
        progress.update_phase("Building search index")
        if len(embeddings_array) > 0:
            self._build_faiss_index(embeddings_array, metadata, vector_ids)

        # Phase 5: Saving
        progress.update_phase("Writing to storage")
        for project_id, records in project_records_map.items():
            for record in records:
                record.embedding_id = record_first_vector_id.get(record.conversation_id, 0)
            self._write_parquet_batch(records, project_id, connector_name_by_file_path)

        self._write_index_metadata(
            len(all_records),
            len(embeddings_array),
            next_vector_id=next_vector_id,
        )

        # Persist indexed source paths for fast watcher startup.
        self._write_indexed_paths({r.file_path for r in all_records})
        if file_state_entries:
            self._write_file_state(file_state_entries)

        # Update final stats
        progress.update_stats(
            conversations=len(all_records),
            chunks=len(all_chunks_with_meta),
            embeddings=len(embeddings_array)
        )
        progress.finish()

        elapsed = time.time() - start_time
        
        parquet_size = sum(
            f.stat().st_size for f in self.conversations_dir.glob("*.parquet")
        ) / (1024 * 1024)
        
        faiss_path = self.indices_dir / "embeddings.faiss"
        faiss_size = faiss_path.stat().st_size / (1024 * 1024) if faiss_path.exists() else 0
        
        return IndexStats(
            total_conversations=len(all_records),
            total_messages=sum(r.message_count for r in all_records),
            index_time_seconds=elapsed,
            parquet_size_mb=parquet_size,
            faiss_size_mb=faiss_size
        )

    def _batch_encode_chunks(
        self,
        chunks_with_meta: list[dict],
        progress: ProgressCallback | None = None,
    ) -> np.ndarray:
        """
        Encode chunks in batches for better performance.
        Uses configured batch_size to avoid memory issues.

        Args:
            chunks_with_meta: List of chunks with metadata
            progress: Optional progress callback

        Returns:
            Embeddings array
        """
        if progress is None:
            progress = NullProgressAdapter()

        if not chunks_with_meta:
            return np.array([])

        texts = [chunk['text'] for chunk in chunks_with_meta]

        # Encode in batches manually to report progress
        all_embeddings = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            embedder = self._get_embedder()
            batch_embeddings = embedder.encode(
                batch,
                batch_size=self.batch_size,
                show_progress_bar=False,
                convert_to_numpy=True
            )
            all_embeddings.extend(batch_embeddings)

            # Update progress
            progress.update_embedding_progress(
                current=min(i + self.batch_size, len(texts)),
                total=len(texts)
            )

        return np.array(all_embeddings)

    @staticmethod
    def _timestamp_ms_to_datetime(value: int | None) -> datetime | None:
        if value is None:
            return None
        try:
            return datetime.fromtimestamp(value / 1000)
        except (OSError, ValueError, TypeError):
            return None

    def _write_parquet_batch(
        self,
        records: list[ConversationRecord],
        project_id: str,
        connector_name_by_file_path: dict[str, str],
    ) -> None:
        output_path = self.conversations_dir / f"project_{project_id}.parquet"
        
        data = {
            'conversation_id': [r.conversation_id for r in records],
            'project_id': [r.project_id for r in records],
            'file_path': [r.file_path for r in records],
            'title': [r.title for r in records],
            'created_at': [r.created_at for r in records],
            'updated_at': [r.updated_at for r in records],
            'message_count': [r.message_count for r in records],
            'messages': [
                [
                    asdict(m)
                    for m in r.messages
                ]
                for r in records
            ],
            'full_text': [r.full_text for r in records],
            'embedding_id': [r.embedding_id for r in records],
            'file_hash': [r.file_hash for r in records],
            'indexed_at': [r.indexed_at for r in records],
            'files_mentioned': [r.files_mentioned for r in records],
            'git_branch': [r.git_branch for r in records],
        }
        
        table = pa.Table.from_pydict(data, schema=CONVERSATION_SCHEMA)
        pq.write_table(table, output_path)

        code_rows: list[dict] = []
        for record in records:
            connector_name = connector_name_by_file_path.get(record.file_path)
            if not connector_name:
                raise RuntimeError(f"Missing connector name for indexed file: {record.file_path}")
            code_rows.extend(self._extract_code_block_dicts(record, connector_name))
        self._write_code_blocks(project_id, code_rows)

    def _record_to_dict(self, record: ConversationRecord) -> dict:
        return {
            "conversation_id": record.conversation_id,
            "project_id": record.project_id,
            "file_path": record.file_path,
            "title": record.title,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "message_count": record.message_count,
            "messages": [
                {
                    "sequence": m.sequence,
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp,
                    "has_code": m.has_code,
                    "code_blocks": m.code_blocks,
                }
                for m in record.messages
            ],
            "full_text": record.full_text,
            "embedding_id": record.embedding_id,
            "file_hash": record.file_hash,
            "indexed_at": record.indexed_at,
            "files_mentioned": record.files_mentioned,
            "git_branch": record.git_branch,
        }

    def _write_project_parquet_dicts(self, project_id: str, record_dicts: list[dict]) -> None:
        output_path = self.conversations_dir / f"project_{project_id}.parquet"
        table = pa.Table.from_pylist(record_dicts, schema=CONVERSATION_SCHEMA)
        pq.write_table(table, output_path)

    def _append_record_dicts(self, project_id: str, record_dicts: list[dict]) -> None:
        if not record_dicts:
            return
        project_parquet = self.conversations_dir / f"project_{project_id}.parquet"
        new_table = pa.Table.from_pylist(record_dicts, schema=CONVERSATION_SCHEMA)
        if project_parquet.exists():
            existing_table = pq.read_table(project_parquet)
            combined_table = pa.concat_tables([existing_table, new_table])
            pq.write_table(combined_table, project_parquet)
        else:
            pq.write_table(new_table, project_parquet)

    def _code_parquet_path(self, project_id: str) -> Path:
        return self.code_dir / f"project_{project_id}.parquet"

    def _write_code_blocks(self, project_id: str, code_rows: list[dict]) -> None:
        path = self._code_parquet_path(project_id)
        table = pa.Table.from_pylist(code_rows, schema=CODE_BLOCK_SCHEMA)
        pq.write_table(table, path)

    def _append_code_blocks(self, project_id: str, code_rows: list[dict]) -> None:
        if not code_rows:
            return
        path = self._code_parquet_path(project_id)
        new_table = pa.Table.from_pylist(code_rows, schema=CODE_BLOCK_SCHEMA)
        if path.exists():
            existing_table = pq.read_table(path)
            combined_table = pa.concat_tables([existing_table, new_table])
            pq.write_table(combined_table, path)
        else:
            pq.write_table(new_table, path)

    def _remove_code_blocks_for_conversation(self, project_id: str, conversation_id: str) -> None:
        path = self._code_parquet_path(project_id)
        if not path.exists():
            return
        table = pq.read_table(path)
        filtered = table.filter(pc.field("conversation_id") != conversation_id)
        pq.write_table(filtered, path)

    def _extract_code_block_dicts(self, record: ConversationRecord, connector_name: str) -> list[dict]:
        from searchat.core.code_extractor import extract_code_blocks

        rows: list[dict] = []
        for message in record.messages:
            extracted = extract_code_blocks(
                message_text=message.content,
                message_index=message.sequence,
                role=message.role,
            )
            for block in extracted:
                rows.append(
                    {
                        "conversation_id": record.conversation_id,
                        "project_id": record.project_id,
                        "connector": connector_name,
                        "file_path": record.file_path,
                        "title": record.title,
                        "conversation_created_at": record.created_at,
                        "conversation_updated_at": record.updated_at,
                        "message_index": block.message_index,
                        "block_index": block.block_index,
                        "role": block.role,
                        "message_timestamp": message.timestamp,
                        "fence_language": block.fence_language,
                        "language": block.language,
                        "language_source": block.language_source,
                        "functions": block.functions,
                        "classes": block.classes,
                        "imports": block.imports,
                        "code": block.code,
                        "code_hash": block.code_hash,
                        "lines": block.lines,
                    }
                )
        return rows

    def _remove_conversation_from_project(self, project_id: str, conversation_id: str) -> None:
        project_parquet = self.conversations_dir / f"project_{project_id}.parquet"
        if not project_parquet.exists():
            return
        table = pq.read_table(project_parquet)
        filtered = table.filter(pc.field("conversation_id") != conversation_id)
        pq.write_table(filtered, project_parquet)

    def _rebuild_idmap_index(
        self,
        existing_index: faiss.Index,
        remaining_ids: list[int],
        new_embeddings: list[np.ndarray],
        new_ids: list[int],
    ) -> faiss.Index:
        dimension = existing_index.d
        base_index = faiss.IndexFlatL2(dimension)  # type: ignore[call-arg]
        rebuilt_index = faiss.IndexIDMap2(base_index)  # type: ignore[call-arg]

        vectors: list[np.ndarray] = []
        ids: list[int] = []

        for vector_id in remaining_ids:
            try:
                vector = existing_index.reconstruct(int(vector_id))  # type: ignore[call-arg]
            except Exception as exc:
                raise RuntimeError(
                    "Failed to reconstruct existing vectors for rebuild."
                ) from exc
            vectors.append(vector)
            ids.append(int(vector_id))

        if new_embeddings:
            vectors.extend(new_embeddings)
            ids.extend(int(vector_id) for vector_id in new_ids)

        if vectors:
            vectors_array = np.vstack(vectors).astype(np.float32)
            ids_array = np.asarray(ids, dtype=np.int64)
            rebuilt_index.add_with_ids(vectors_array, ids_array)  # type: ignore[call-arg]

        return rebuilt_index

    def delete_conversations(
        self,
        conversation_ids: list[str],
        delete_source_files: bool = False,
    ) -> dict:
        """Delete conversations from all storage layers.

        Args:
            conversation_ids: IDs to delete.
            delete_source_files: If True, also delete original source files from disk.

        Returns:
            Summary dict with deleted count, removed vectors, and source files deleted.
        """
        if not conversation_ids:
            raise ValueError("conversation_ids must not be empty")

        deletion_set = set(conversation_ids)

        # 2. Resolve project_ids and file_paths from conversation parquets
        project_to_cids: dict[str, set[str]] = {}
        cid_to_file_path: dict[str, str] = {}

        for parquet_file in self.conversations_dir.glob("project_*.parquet"):
            table = pq.read_table(
                parquet_file,
                columns=["conversation_id", "project_id", "file_path"],
            )
            for row in table.to_pylist():
                cid = row["conversation_id"]
                if cid in deletion_set:
                    pid = row["project_id"]
                    project_to_cids.setdefault(pid, set()).add(cid)
                    if row.get("file_path"):
                        cid_to_file_path[cid] = row["file_path"]

        # 3. Remove from conversation parquets
        for project_id, cids in project_to_cids.items():
            for cid in cids:
                self._remove_conversation_from_project(project_id, cid)

        # 4. Remove code blocks
        for project_id, cids in project_to_cids.items():
            for cid in cids:
                self._remove_code_blocks_for_conversation(project_id, cid)

        # 5. Filter embeddings metadata and collect removed vector IDs
        removed_vector_ids: list[int] = []
        metadata_path = self.indices_dir / "embeddings.metadata.parquet"
        if metadata_path.exists() and metadata_path.stat().st_size > 0:
            meta_table = pq.read_table(metadata_path)
            cid_col = meta_table.column("conversation_id")
            mask = pc.invert(pc.is_in(cid_col, value_set=pa.array(list(deletion_set))))
            removed_mask = pc.is_in(cid_col, value_set=pa.array(list(deletion_set)))
            removed_rows = meta_table.filter(removed_mask)
            removed_vector_ids = removed_rows.column("vector_id").to_pylist()
            filtered_meta = meta_table.filter(mask)
            pq.write_table(filtered_meta, metadata_path)

        # 6. Rebuild FAISS index
        faiss_path = self.indices_dir / "embeddings.faiss"
        if faiss_path.exists() and removed_vector_ids:
            existing_index = faiss.read_index(str(faiss_path))
            # Read remaining IDs from the filtered metadata
            if metadata_path.exists():
                remaining_meta = pq.read_table(metadata_path, columns=["vector_id"])
                remaining_ids = remaining_meta.column("vector_id").to_pylist()
            else:
                remaining_ids = []
            # Ensure direct map for vector reconstruction
            try:
                existing_index.make_direct_map()
            except Exception:
                pass
            rebuilt = self._rebuild_idmap_index(
                existing_index, remaining_ids, new_embeddings=[], new_ids=[]
            )
            faiss.write_index(rebuilt, str(faiss_path))

        # 7. Update file_state.parquet
        if self.file_state_path.exists():
            fs_table = pq.read_table(self.file_state_path)
            if "conversation_id" in fs_table.column_names:
                fs_mask = pc.invert(
                    pc.is_in(
                        fs_table.column("conversation_id"),
                        value_set=pa.array(list(deletion_set)),
                    )
                )
                pq.write_table(fs_table.filter(fs_mask), self.file_state_path)

        # 8. Update indexed_paths.parquet
        remaining_paths = self.get_indexed_file_paths()
        deleted_paths = set(cid_to_file_path.values())
        remaining_paths -= deleted_paths
        if remaining_paths:
            self._write_indexed_paths(remaining_paths)
        elif self.indexed_paths_path.exists():
            self.indexed_paths_path.unlink()

        # 9. Update index metadata
        existing_meta = self._load_existing_metadata()
        if existing_meta:
            total_deleted = sum(len(cids) for cids in project_to_cids.values())
            existing_meta["total_conversations"] = max(
                0, existing_meta.get("total_conversations", 0) - total_deleted
            )
            existing_meta["total_chunks"] = max(
                0, existing_meta.get("total_chunks", 0) - len(removed_vector_ids)
            )
            existing_meta["last_updated"] = datetime.now().isoformat()
            metadata_json_path = self.indices_dir / "index_metadata.json"
            with open(metadata_json_path, "w", encoding="utf-8") as f:
                json.dump(existing_meta, f, indent=2)

        # 10. Delete source files if requested
        source_files_deleted = 0
        if delete_source_files:
            for cid in conversation_ids:
                fp = cid_to_file_path.get(cid)
                if not fp:
                    continue
                # Skip pseudo-paths (e.g. Cursor's SQLite-based paths)
                if "#.vscdb.cursor/" in fp:
                    continue
                source_path = Path(fp)
                if source_path.is_file():
                    source_path.unlink()
                    source_files_deleted += 1
                    logger.info("Deleted source file: %s", fp)
                else:
                    logger.warning("Source file not found (may be already removed): %s", fp)

        deleted_count = sum(len(cids) for cids in project_to_cids.values())
        logger.info(
            "Deleted %d conversations, removed %d vectors, deleted %d source files",
            deleted_count, len(removed_vector_ids), source_files_deleted,
        )

        return {
            "deleted": deleted_count,
            "removed_vectors": len(removed_vector_ids),
            "source_files_deleted": source_files_deleted,
        }

    def _build_faiss_index(
        self,
        embeddings: np.ndarray,
        metadata: list[dict],
        vector_ids: list[int],
    ) -> None:
        dimension = embeddings.shape[1]  # type: ignore[call-arg]
        n_vectors = embeddings.shape[0]  # type: ignore[call-arg]

        if n_vectors < 100:
            base_index = faiss.IndexFlatL2(dimension)  # type: ignore[call-arg]
        else:
            quantizer = faiss.IndexFlatL2(dimension)  # type: ignore[call-arg]
            base_index = faiss.IndexIVFFlat(quantizer, dimension, min(100, n_vectors // 10))  # type: ignore[call-arg]
            base_index.train(embeddings)  # type: ignore[call-arg,arg-type]

        index = faiss.IndexIDMap2(base_index)  # type: ignore[call-arg]
        id_array = np.asarray(vector_ids, dtype=np.int64)
        index.add_with_ids(embeddings, id_array)  # type: ignore[call-arg,arg-type]

        faiss.write_index(index, str(self.indices_dir / "embeddings.faiss"))  # type: ignore[call-arg]

        metadata_table = pa.Table.from_pylist(metadata, schema=METADATA_SCHEMA)  # type: ignore[call-arg]
        pq.write_table(metadata_table, self.indices_dir / "embeddings.metadata.parquet")  # type: ignore[call-arg]
    
    def _write_index_metadata(
        self,
        total_conversations: int,
        total_chunks: int,
        *,
        created_at: str | None = None,
        next_vector_id: int | None = None,
    ) -> None:
        if created_at is None:
            created_at = datetime.now().isoformat()
        if next_vector_id is None:
            next_vector_id = total_chunks

        metadata = {
            "schema_version": INDEX_SCHEMA_VERSION,
            "index_format_version": INDEX_FORMAT_VERSION,
            "created_at": created_at,
            "embedding_model": self.config.embedding.model,
            "format": INDEX_FORMAT,
            "last_updated": datetime.now().isoformat(),
            "total_conversations": total_conversations,
            "total_chunks": total_chunks,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "next_vector_id": next_vector_id,
        }

        metadata_path = self.indices_dir / INDEX_METADATA_FILENAME
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
    
    def _has_existing_index(self) -> bool:
        """Check if an existing index is present."""
        metadata_path = self.indices_dir / INDEX_METADATA_FILENAME
        faiss_path = self.indices_dir / "embeddings.faiss"
        has_parquets = any(self.conversations_dir.glob("*.parquet"))

        return metadata_path.exists() or faiss_path.exists() or has_parquets

    def _load_existing_metadata(self) -> dict | None:
        metadata_path = self.indices_dir / INDEX_METADATA_FILENAME
        if not metadata_path.exists():
            return None
        
        with open(metadata_path, 'r') as f:
            return json.load(f)

    def _require_compatible_index(self, metadata: dict) -> None:
        if metadata.get("embedding_model") != self.config.embedding.model:
            raise ValueError(
                f"Model mismatch: index uses '{metadata.get('embedding_model')}', "
                f"config specifies '{self.config.embedding.model}'. "
                "Cannot append with different embedding model."
            )
        if metadata.get("format") != INDEX_FORMAT:
            raise ValueError(
                f"Index format mismatch: index uses '{metadata.get('format')}', "
                f"expected '{INDEX_FORMAT}'. Rebuild index required."
            )
        if metadata.get("schema_version") != INDEX_SCHEMA_VERSION:
            raise ValueError(
                f"Schema version mismatch: index uses version {metadata.get('schema_version')}, "
                f"expected version {INDEX_SCHEMA_VERSION}. Rebuild index required."
            )
        if metadata.get("index_format_version") != INDEX_FORMAT_VERSION:
            raise ValueError(
                f"Index format version mismatch: index uses version {metadata.get('index_format_version')}, "
                f"expected version {INDEX_FORMAT_VERSION}. Rebuild index required."
            )
    
    def get_indexed_file_paths(self) -> set:
        """
        Get set of all indexed file paths.

        Returns:
            Set of file path strings that are already in the index
        """
        if self.indexed_paths_path.exists():
            table = pq.read_table(self.indexed_paths_path, columns=["file_path"])
            return set(table.column("file_path").to_pylist())

        indexed_paths: set[str] = set()

        for parquet_file in self.conversations_dir.glob("*.parquet"):
            table = pq.read_table(parquet_file, columns=["file_path"])
            indexed_paths.update(table.column("file_path").to_pylist())

        # Backfill the fast path if possible.
        if indexed_paths:
            self._write_indexed_paths(indexed_paths)

        return indexed_paths

    def _extract_expertise(
        self,
        conversation_records: dict[str, list[ConversationRecord]],
        progress: ProgressCallback,
    ) -> None:
        """Run heuristic expertise extraction on newly indexed conversations.

        Best-effort: logs errors but never blocks the indexing pipeline.
        """
        if not self.config.expertise.enabled:
            return

        all_records = [r for batch in conversation_records.values() for r in batch]
        if not all_records:
            return

        try:
            from searchat.expertise.pipeline import create_pipeline

            pipeline = create_pipeline(self.config, self.search_dir)
            batch = [
                {
                    "full_text": r.full_text,
                    "conversation_id": r.conversation_id,
                    "project_id": r.project_id,
                }
                for r in all_records
            ]
            progress.update_phase("Extracting expertise")
            stats = pipeline.extract_batch(batch, mode="heuristic_only")
            logger.info(
                "Expertise extraction: %d processed, %d created, %d reinforced",
                stats.conversations_processed,
                stats.records_created,
                stats.records_reinforced,
            )
        except Exception as exc:
            logger.error("Expertise extraction failed (non-blocking): %s", exc)

    def index_append_only(
        self,
        file_paths: list[str],
        progress: ProgressCallback | None = None,
    ) -> UpdateStats:
        """
        Append-only indexing for new conversation files.

        SAFETY: This method ONLY adds new data. It never modifies or deletes
        existing indexed data. Safe to call even with orphaned parquet data.

        Supports both Claude Code (.jsonl) and Mistral Vibe (.json) files.

        Args:
            file_paths: List of conversation file paths to index
            progress: Optional progress callback

        Returns:
            UpdateStats with indexing results
        """
        if progress is None:
            progress = NullProgressAdapter()
        if not self.config.indexing.enable_connectors:
            raise RuntimeError(
                "Connector loading is disabled. Set indexing.enable_connectors to true."
            )

        progress.update_phase("Processing new conversations")
        start_time = time.time()

        existing_metadata = self._load_existing_metadata()
        if existing_metadata is None:
            raise RuntimeError(
                "No existing index found. Cannot append to non-existent index. "
                "Initial index must exist before append-only mode can be used."
            )

        self._require_compatible_index(existing_metadata)

        # Get already indexed paths to skip duplicates
        existing_paths = self.get_indexed_file_paths()

        # Filter to only truly new files
        new_files = [f for f in file_paths if f not in existing_paths]

        if not new_files:
            return UpdateStats(
                new_conversations=0,
                updated_conversations=0,
                skipped_conversations=len(file_paths),
                update_time_seconds=time.time() - start_time
            )

        # Load existing FAISS index
        faiss_path = self.indices_dir / "embeddings.faiss"
        existing_index = faiss.read_index(str(faiss_path))

        # Load existing metadata
        existing_metadata_table = pq.read_table(
            self.indices_dir / "embeddings.metadata.parquet"
        )
        existing_metadata_df = existing_metadata_table.to_pandas()
        next_vector_id = int(existing_metadata.get("next_vector_id", 0) or 0)
        existing_ids = existing_metadata_table.column("vector_id").to_pylist()
        max_vector_id = max(existing_ids) if existing_ids else -1
        if next_vector_id <= max_vector_id:
            next_vector_id = max_vector_id + 1

        new_embeddings = []
        new_metadata = []
        new_vector_ids: list[int] = []
        new_conversation_records: dict[str, list[ConversationRecord]] = {}
        new_indexed_paths: set[str] = set()
        connector_name_by_file_path: dict[str, str] = {}
        processed_count = 0
        empty_count = 0

        for idx, file_path in enumerate(new_files, 1):
            json_path = Path(file_path)

            if not json_path.exists():
                logger.warning(f"File not found, skipping: {file_path}")
                continue

            try:
                connector = detect_connector(json_path)
            except ValueError as exc:
                progress.update_file_progress(idx, len(new_files), f"unknown | {json_path.name}")
                logger.warning("%s; skipping: %s", exc, file_path)
                continue

            display_name = f"{connector.name} | {json_path.name}"
            progress.update_file_progress(idx, len(new_files), display_name)

            try:
                record = connector.parse(json_path, next_vector_id)

                # Skip conversations with no messages
                if record.message_count == 0:
                    empty_count += 1
                    continue

                new_indexed_paths.add(record.file_path)

                connector_name_by_file_path[record.file_path] = connector.name

                project_key = record.project_id
                if project_key not in new_conversation_records:
                    new_conversation_records[project_key] = []
                new_conversation_records[project_key].append(record)

                chunks_with_meta = self._chunk_by_messages(record.messages, record.title)

                # Batch encode all chunks for this conversation
                chunk_embeddings = self._batch_encode_chunks(chunks_with_meta, progress)

                for chunk_idx, (chunk_meta, embedding) in enumerate(zip(chunks_with_meta, chunk_embeddings)):
                    new_embeddings.append(embedding)

                    new_metadata.append({
                        'vector_id': next_vector_id,
                        'conversation_id': record.conversation_id,
                        'project_id': record.project_id,
                        'chunk_index': chunk_idx,
                        'chunk_text': chunk_meta['text'],
                        'message_start_index': chunk_meta['start_message_index'],
                        'message_end_index': chunk_meta['end_message_index'],
                        'created_at': record.created_at
                    })
                    new_vector_ids.append(next_vector_id)
                    next_vector_id += 1

                processed_count += 1

            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}")
                continue

        # Append to FAISS index
        if new_embeddings:
            embeddings_array = np.array(new_embeddings).astype(np.float32)
            id_array = np.asarray(new_vector_ids, dtype=np.int64)
            try:
                existing_index.add_with_ids(embeddings_array, id_array)
                faiss.write_index(existing_index, str(faiss_path))
            except Exception:
                remaining_ids = [
                    int(value)
                    for value in existing_metadata_table.column("vector_id").to_pylist()
                    if value is not None
                ]
                rebuilt_index = self._rebuild_idmap_index(
                    existing_index,
                    remaining_ids,
                    new_embeddings,
                    new_vector_ids,
                )
                faiss.write_index(rebuilt_index, str(faiss_path))

            # Append to metadata parquet
            new_metadata_table = pa.Table.from_pylist(new_metadata, schema=METADATA_SCHEMA)
            combined_metadata = pa.concat_tables([existing_metadata_table, new_metadata_table])
            pq.write_table(combined_metadata, self.indices_dir / "embeddings.metadata.parquet")

        # Append to conversation parquets
        for project_id, records in new_conversation_records.items():
            new_record_dicts = [self._record_to_dict(r) for r in records]
            self._append_record_dicts(project_id, new_record_dicts)

            code_rows: list[dict] = []
            for record in records:
                connector_name = connector_name_by_file_path.get(record.file_path)
                if not connector_name:
                    raise RuntimeError(f"Missing connector name for indexed file: {record.file_path}")
                code_rows.extend(self._extract_code_block_dicts(record, connector_name))
            self._append_code_blocks(project_id, code_rows)

        # Update index metadata
        existing_index_metadata = self._load_existing_metadata()
        if existing_index_metadata is None:
            raise RuntimeError("Index metadata missing after append-only update")
        total_conversations = existing_index_metadata["total_conversations"] + processed_count
        total_chunks = existing_index_metadata["total_chunks"] + len(new_embeddings)
        created_at = existing_index_metadata.get("created_at") or datetime.now().isoformat()
        self._write_index_metadata(
            total_conversations,
            total_chunks,
            created_at=created_at,
            next_vector_id=next_vector_id,
        )

        progress.update_stats(
            conversations=processed_count,
            chunks=len(new_embeddings),
            embeddings=len(new_embeddings)
        )
        progress.finish()

        if new_indexed_paths:
            self._write_indexed_paths(existing_paths | new_indexed_paths)

        if new_conversation_records:
            file_state = self._load_file_state()
            if not file_state:
                file_state = self._backfill_file_state()
            for records in new_conversation_records.values():
                for record in records:
                    path_obj = Path(record.file_path)
                    file_size = path_obj.stat().st_size if path_obj.exists() else 0
                    connector_name = connector_name_by_file_path.get(record.file_path)
                    if not connector_name:
                        raise RuntimeError(f"Missing connector name for indexed file: {record.file_path}")
                    file_state[record.file_path] = {
                        "file_path": record.file_path,
                        "file_hash": record.file_hash,
                        "file_size": file_size,
                        "indexed_at": record.indexed_at,
                        "connector_name": connector_name,
                        "conversation_id": record.conversation_id,
                        "project_id": record.project_id,
                    }
            self._write_file_state(list(file_state.values()))

        # Run expertise extraction on newly indexed conversations
        self._extract_expertise(new_conversation_records, progress)

        elapsed = time.time() - start_time

        return UpdateStats(
            new_conversations=processed_count,
            updated_conversations=0,
            skipped_conversations=len(file_paths) - processed_count - empty_count,
            update_time_seconds=elapsed,
            empty_conversations=empty_count,
        )

    def index_adaptive(
        self,
        file_paths: list[str],
        progress: ProgressCallback | None = None,
    ) -> UpdateStats:
        """
        Adaptive indexing for new and modified conversation files.

        New files are appended. Modified files trigger per-conversation reindexing.
        """
        if progress is None:
            progress = NullProgressAdapter()
        if not self.config.indexing.enable_connectors:
            raise RuntimeError(
                "Connector loading is disabled. Set indexing.enable_connectors to true."
            )
        if not self.config.indexing.enable_adaptive_indexing:
            return self.index_append_only(file_paths, progress)

        progress.update_phase("Processing conversations")
        start_time = time.time()

        existing_metadata = self._load_existing_metadata()
        if existing_metadata is None:
            raise RuntimeError(
                "No existing index found. Cannot perform adaptive update. "
                "Initial index must exist before adaptive mode can be used."
            )

        self._require_compatible_index(existing_metadata)

        faiss_path = self.indices_dir / "embeddings.faiss"
        existing_index = faiss.read_index(str(faiss_path))

        existing_metadata_table = pq.read_table(
            self.indices_dir / "embeddings.metadata.parquet"
        )

        file_state = self._load_file_state()
        if not file_state:
            file_state = self._backfill_file_state()

        next_vector_id = int(existing_metadata.get("next_vector_id", 0) or 0)
        existing_ids = existing_metadata_table.column("vector_id").to_pylist()
        max_vector_id = max(existing_ids) if existing_ids else -1
        if next_vector_id <= max_vector_id:
            next_vector_id = max_vector_id + 1

        new_embeddings: list[np.ndarray] = []
        new_metadata: list[dict] = []
        new_vector_ids: list[int] = []
        records_to_append: dict[str, list[ConversationRecord]] = {}
        removed_vector_ids: set[int] = set()
        connector_name_by_file_path: dict[str, str] = {}

        new_count = 0
        updated_count = 0
        skipped_count = 0

        for idx, file_path in enumerate(file_paths, 1):
            json_path = Path(file_path)
            if not json_path.exists():
                logger.warning(f"File not found, skipping: {file_path}")
                skipped_count += 1
                continue

            connector = detect_connector(json_path)
            display_name = f"{connector.name} | {json_path.name}"
            progress.update_file_progress(idx, len(file_paths), display_name)

            file_hash = hashlib.sha256(json_path.read_bytes()).hexdigest()
            file_size = json_path.stat().st_size
            existing_state = file_state.get(file_path)
            if existing_state and existing_state.get("file_hash") == file_hash:
                skipped_count += 1
                continue

            record = connector.parse(json_path, next_vector_id)
            if record.message_count == 0:
                skipped_count += 1
                continue

            old_conversation_id = None
            old_project_id = None
            if existing_state:
                old_conversation_id = existing_state.get("conversation_id")
                old_project_id = existing_state.get("project_id")

            if isinstance(old_conversation_id, str):
                mask = pc.equal(existing_metadata_table["conversation_id"], old_conversation_id)  # type: ignore[attr-defined]
                filtered_rows = existing_metadata_table.filter(mask)
                removed_vector_ids.update(
                    value for value in filtered_rows.column("vector_id").to_pylist() if value is not None
                )
                existing_metadata_table = existing_metadata_table.filter(pc.invert(mask))  # type: ignore[attr-defined]
                if isinstance(old_project_id, str):
                    self._remove_conversation_from_project(old_project_id, old_conversation_id)
                    self._remove_code_blocks_for_conversation(old_project_id, old_conversation_id)
                updated_count += 1
            else:
                new_count += 1

            chunks_with_meta = self._chunk_by_messages(record.messages, record.title)
            record.embedding_id = next_vector_id
            chunk_embeddings = self._batch_encode_chunks(chunks_with_meta, progress)
            for chunk_idx, (chunk_meta, embedding) in enumerate(zip(chunks_with_meta, chunk_embeddings)):
                new_embeddings.append(embedding)
                new_metadata.append({
                    "vector_id": next_vector_id,
                    "conversation_id": record.conversation_id,
                    "project_id": record.project_id,
                    "chunk_index": chunk_idx,
                    "chunk_text": chunk_meta["text"],
                    "message_start_index": chunk_meta["start_message_index"],
                    "message_end_index": chunk_meta["end_message_index"],
                    "created_at": record.created_at,
                })
                new_vector_ids.append(next_vector_id)
                next_vector_id += 1

            records_to_append.setdefault(record.project_id, []).append(record)
            connector_name_by_file_path[record.file_path] = connector.name
            file_state[record.file_path] = {
                "file_path": record.file_path,
                "file_hash": file_hash,
                "file_size": file_size,
                "indexed_at": record.indexed_at,
                "connector_name": connector.name,
                "conversation_id": record.conversation_id,
                "project_id": record.project_id,
            }

        # NOTE: We intentionally do not call `faiss.Index.remove_ids()` here.
        # Several FAISS builds can abort the process on remove_ids for IndexIDMap/IVF
        # combinations, which is not catchable from Python. Instead we make semantic
        # deletion append-only: drop rows from the metadata parquet so stale vectors
        # can no longer join to conversations. This keeps indexing crash-free and
        # preserves the project's "never delete data" safety posture.
        needs_rebuild = False

        if new_embeddings:
            embeddings_array = np.array(new_embeddings).astype(np.float32)
            id_array = np.asarray(new_vector_ids, dtype=np.int64)
            try:
                if not needs_rebuild:
                    existing_index.add_with_ids(embeddings_array, id_array)
                    faiss.write_index(existing_index, str(faiss_path))
            except Exception:
                needs_rebuild = True

        if needs_rebuild:
            remaining_ids = [
                int(value)
                for value in existing_metadata_table.column("vector_id").to_pylist()
                if value is not None
            ]
            rebuilt_index = self._rebuild_idmap_index(
                existing_index,
                remaining_ids,
                new_embeddings,
                new_vector_ids,
            )
            faiss.write_index(rebuilt_index, str(faiss_path))

        if new_metadata or removed_vector_ids:
            filtered_metadata = existing_metadata_table.to_pylist()
            combined_metadata = filtered_metadata + new_metadata
            updated_table = pa.Table.from_pylist(combined_metadata, schema=METADATA_SCHEMA)
            pq.write_table(updated_table, self.indices_dir / "embeddings.metadata.parquet")

        for project_id, records in records_to_append.items():
            record_dicts = [self._record_to_dict(r) for r in records]
            self._append_record_dicts(project_id, record_dicts)

            code_rows: list[dict] = []
            for record in records:
                connector_name = connector_name_by_file_path.get(record.file_path)
                if not connector_name:
                    raise RuntimeError(f"Missing connector name for indexed file: {record.file_path}")
                code_rows.extend(self._extract_code_block_dicts(record, connector_name))
            self._append_code_blocks(project_id, code_rows)

        if file_state:
            self._write_file_state(list(file_state.values()))

        existing_paths = self.get_indexed_file_paths()
        if records_to_append:
            new_paths = {r.file_path for records in records_to_append.values() for r in records}
            if new_paths:
                self._write_indexed_paths(existing_paths | new_paths)

        total_conversations = existing_metadata["total_conversations"] + new_count
        total_chunks = len(existing_metadata_table) + len(new_metadata)
        created_at = existing_metadata.get("created_at") or datetime.now().isoformat()
        self._write_index_metadata(
            total_conversations,
            total_chunks,
            created_at=created_at,
            next_vector_id=next_vector_id,
        )

        progress.update_stats(
            conversations=new_count + updated_count,
            chunks=len(new_metadata),
            embeddings=len(new_metadata),
        )
        progress.finish()

        elapsed = time.time() - start_time

        return UpdateStats(
            new_conversations=new_count,
            updated_conversations=updated_count,
            skipped_conversations=skipped_count,
            update_time_seconds=elapsed,
        )
