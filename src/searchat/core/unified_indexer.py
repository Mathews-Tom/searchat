"""UnifiedIndexer — DuckDB-native conversation indexer with exchange-level segmentation.

Replaces ConversationIndexer (Parquet+FAISS) by writing directly to DuckDB via
UnifiedStorage. Each user→assistant exchange becomes its own searchable unit with
a dedicated HNSW embedding.

Implements the IndexingBackend protocol from searchat.contracts.indexing.
"""
from __future__ import annotations

import hashlib
import time
from datetime import datetime
from pathlib import Path

from searchat.config import Config
from searchat.core.connectors import detect_connector, discover_all_files
from searchat.core.logging_config import get_logger
from searchat.core.progress import NullProgressAdapter, ProgressCallback
from searchat.models import ConversationRecord, IndexStats, UpdateStats
from searchat.storage.unified_storage import UnifiedStorage

logger = get_logger(__name__)


def _derive_exchange_id(conversation_id: str, ply_start: int, ply_end: int) -> str:
    """Deterministic exchange ID from conversation + ply range."""
    return hashlib.sha256(
        f"{conversation_id}:{ply_start}:{ply_end}".encode()
    ).hexdigest()[:16]


def _segment_exchanges(
    conversation_id: str,
    project_id: str,
    messages: list[dict],
    fallback_time: datetime,
) -> list[dict]:
    """Segment a flat message list into user→assistant exchanges.

    An exchange starts at each 'user' message and spans through subsequent
    'assistant' messages until the next 'user' or end of conversation.
    """
    if not messages:
        return []

    exchanges: list[dict] = []
    current_start: int | None = None
    current_texts: list[str] = []

    for msg in messages:
        seq = msg["sequence"]
        role = msg["role"]

        if role == "user":
            if current_start is not None and current_texts:
                ply_end = seq - 1
                exchange_text = "\n\n".join(current_texts)
                exchanges.append({
                    "exchange_id": _derive_exchange_id(conversation_id, current_start, ply_end),
                    "conversation_id": conversation_id,
                    "project_id": project_id,
                    "ply_start": current_start,
                    "ply_end": ply_end,
                    "exchange_text": exchange_text,
                    "created_at": fallback_time,
                })
            current_start = seq
            current_texts = [msg["content"]]
        else:
            if current_start is None:
                current_start = seq
                current_texts = []
            current_texts.append(msg["content"])

    if current_start is not None and current_texts:
        ply_end = messages[-1]["sequence"]
        exchange_text = "\n\n".join(current_texts)
        exchanges.append({
            "exchange_id": _derive_exchange_id(conversation_id, current_start, ply_end),
            "conversation_id": conversation_id,
            "project_id": project_id,
            "ply_start": current_start,
            "ply_end": ply_end,
            "exchange_text": exchange_text,
            "created_at": fallback_time,
        })

    return exchanges


class UnifiedIndexer:
    """DuckDB-native indexer implementing IndexingBackend protocol.

    Writes directly to DuckDB via UnifiedStorage. Segments conversations
    into exchanges and generates per-exchange HNSW embeddings.

    Safety: index_all() raises RuntimeError (same guard as ConversationIndexer).
    """

    def __init__(
        self,
        search_dir: Path,
        config: Config | None = None,
        *,
        storage: UnifiedStorage | None = None,
    ) -> None:
        self.search_dir = search_dir
        if config is None:
            config = Config.load()
        self.config = config

        if storage is not None:
            self._storage = storage
        else:
            db_path = config.storage.resolve_duckdb_path(search_dir)
            self._storage = UnifiedStorage(
                db_path,
                hnsw_ef_construction=config.storage.hnsw_ef_construction,
                hnsw_ef_search=config.storage.hnsw_ef_search,
                hnsw_m=config.storage.hnsw_m,
            )

        self._embedder = None

    @property
    def storage(self) -> UnifiedStorage:
        return self._storage

    def _get_embedder(self):
        """Create and cache the embedding model on first use."""
        if self._embedder is not None:
            return self._embedder

        from searchat.gpu_check import check_and_warn_gpu
        check_and_warn_gpu()

        from sentence_transformers import SentenceTransformer

        device = self.config.embedding.get_device()
        logger.info("Initializing embedding model on device: %s", device)
        self._embedder = SentenceTransformer(self.config.embedding.model, device=device)
        return self._embedder

    def index_all(
        self,
        force: bool = False,
        progress: ProgressCallback | None = None,
    ) -> IndexStats:
        """SAFETY GUARD: Full rebuild is blocked to protect irreplaceable data.

        Raises RuntimeError unconditionally — same message as ConversationIndexer.
        """
        raise RuntimeError(
            "Existing index detected. Full rebuild will REPLACE all indexed data.\n\n"
            "If source JSONLs are missing or incomplete, you will lose conversations.\n\n"
            "Options:\n"
            "  1. Use index_append_only() to safely add new conversations\n"
            "  2. Call index_all(force=True) if you have complete source files\n"
            "  3. Delete index manually: rm -rf <search_dir>/data/\n\n"
            f"Index location: {self.search_dir / 'data'}"
        )

    def index_append_only(
        self,
        file_paths: list[str],
        progress: ProgressCallback | None = None,
    ) -> UpdateStats:
        """Append-only indexing: adds new conversations to DuckDB.

        Writes conversations, messages, exchanges, embeddings, code blocks,
        and file state directly to DuckDB via UnifiedStorage.

        Never modifies or deletes existing data.
        """
        if progress is None:
            progress = NullProgressAdapter()
        if not self.config.indexing.enable_connectors:
            raise RuntimeError(
                "Connector loading is disabled. Set indexing.enable_connectors to true."
            )

        progress.update_phase("Processing new conversations")
        start_time = time.time()

        indexed_paths = self.get_indexed_file_paths()
        new_files = [f for f in file_paths if f not in indexed_paths]

        if not new_files:
            return UpdateStats(
                new_conversations=0,
                updated_conversations=0,
                skipped_conversations=len(file_paths),
                update_time_seconds=time.time() - start_time,
            )

        processed_count = 0
        empty_count = 0
        total_exchanges = 0
        total_embeddings = 0

        for idx, file_path in enumerate(new_files, 1):
            json_path = Path(file_path)
            if not json_path.exists():
                logger.warning("File not found, skipping: %s", file_path)
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
                record = connector.parse(json_path, 0)

                if record.message_count == 0:
                    empty_count += 1
                    continue

                # Write conversation to DuckDB
                self._write_conversation(record)

                # Write messages
                msg_dicts = self._record_messages_to_dicts(record)
                self._storage.insert_messages(record.conversation_id, msg_dicts)

                # Segment into exchanges and write
                exchanges = _segment_exchanges(
                    record.conversation_id,
                    record.project_id,
                    msg_dicts,
                    record.created_at,
                )
                for exc in exchanges:
                    self._storage.upsert_exchange(**exc)
                total_exchanges += len(exchanges)

                # Generate and store embeddings for exchanges
                if exchanges:
                    n_embedded = self._embed_exchanges(exchanges, progress)
                    total_embeddings += n_embedded

                # Write code blocks
                self._write_code_blocks(record, connector.name)

                # Write file state
                file_size = json_path.stat().st_size if json_path.exists() else 0
                self._storage.upsert_file_state(
                    file_path=record.file_path,
                    conversation_id=record.conversation_id,
                    project_id=record.project_id,
                    connector_name=connector.name,
                    file_size=file_size,
                    file_hash=record.file_hash,
                )

                processed_count += 1

            except Exception as e:
                logger.error("Failed to process %s: %s", file_path, e)
                continue

        # Run expertise extraction
        if processed_count > 0:
            self._run_expertise_extraction(progress)

        progress.update_stats(
            conversations=processed_count,
            chunks=total_exchanges,
            embeddings=total_embeddings,
        )
        progress.finish()

        elapsed = time.time() - start_time

        return UpdateStats(
            new_conversations=processed_count,
            updated_conversations=0,
            skipped_conversations=len(file_paths) - processed_count - empty_count,
            update_time_seconds=elapsed,
            empty_conversations=empty_count,
        )

    def index_from_source_files(
        self,
        progress: ProgressCallback | None = None,
    ) -> UpdateStats:
        """Discover and index all un-indexed source files.

        Convenience method used by the watcher and daemon: discovers files
        from all connectors, filters to un-indexed, and calls index_append_only.
        """
        if progress is None:
            progress = NullProgressAdapter()
        if not self.config.indexing.enable_connectors:
            raise RuntimeError(
                "Connector loading is disabled. Set indexing.enable_connectors to true."
            )

        progress.update_phase("Discovering conversation files")
        all_files: list[str] = []
        for match in discover_all_files(self.config):
            all_files.append(str(match.path))

        return self.index_append_only(all_files, progress)

    def get_indexed_file_paths(self) -> set:
        """Return set of file paths already indexed in DuckDB."""
        try:
            cur = self._storage._read_cursor()
            rows = cur.execute(
                "SELECT file_path FROM source_file_state WHERE status = 'indexed'"
            ).fetchall()
            return {row[0] for row in rows}
        except Exception:
            return set()

    def _write_conversation(self, record: ConversationRecord) -> None:
        """Write a ConversationRecord to DuckDB conversations table."""
        self._storage.upsert_conversation(
            conversation_id=record.conversation_id,
            project_id=record.project_id,
            file_path=record.file_path,
            title=record.title,
            created_at=record.created_at,
            updated_at=record.updated_at,
            message_count=record.message_count,
            full_text=record.full_text,
            file_hash=record.file_hash,
            indexed_at=record.indexed_at,
            files_mentioned=record.files_mentioned,
            git_branch=record.git_branch,
        )

    @staticmethod
    def _record_messages_to_dicts(record: ConversationRecord) -> list[dict]:
        """Convert MessageRecords to dicts suitable for DuckDB insert."""
        return [
            {
                "sequence": m.sequence,
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp,
                "has_code": m.has_code,
                "code_blocks": m.code_blocks,
            }
            for m in record.messages
        ]

    def _embed_exchanges(
        self,
        exchanges: list[dict],
        progress: ProgressCallback,
    ) -> int:
        """Generate embeddings for exchanges and store in DuckDB."""
        texts = [exc["exchange_text"] for exc in exchanges]
        embedder = self._get_embedder()

        batch_size = self.config.embedding.batch_size
        embedded = 0

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            embeddings = embedder.encode(
                batch,
                batch_size=batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
            )

            for j, embedding in enumerate(embeddings):
                exc = exchanges[i + j]
                vec = embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)
                self._storage.upsert_embedding(exc["exchange_id"], vec)
                embedded += 1

            progress.update_embedding_progress(
                current=min(i + batch_size, len(texts)),
                total=len(texts),
            )

        return embedded

    def _write_code_blocks(self, record: ConversationRecord, connector_name: str) -> None:
        """Extract and write code blocks from a conversation to DuckDB."""
        from searchat.core.code_extractor import extract_code_blocks

        for message in record.messages:
            extracted = extract_code_blocks(
                message_text=message.content,
                message_index=message.sequence,
                role=message.role,
            )
            for block in extracted:
                self._storage.insert_code_block(
                    conversation_id=record.conversation_id,
                    project_id=record.project_id,
                    connector=connector_name,
                    file_path=record.file_path,
                    title=record.title,
                    conversation_created_at=record.created_at,
                    conversation_updated_at=record.updated_at,
                    message_index=block.message_index,
                    block_index=block.block_index,
                    role=block.role,
                    message_timestamp=message.timestamp,
                    fence_language=block.fence_language,
                    language=block.language,
                    language_source=block.language_source,
                    functions=block.functions,
                    classes=block.classes,
                    imports=block.imports,
                    code=block.code,
                    code_hash=block.code_hash,
                    lines=block.lines,
                )

    def _run_expertise_extraction(self, progress: ProgressCallback) -> None:
        """Best-effort expertise extraction on newly indexed conversations."""
        if not self.config.expertise.enabled:
            return

        try:
            from searchat.expertise.pipeline import create_pipeline

            pipeline = create_pipeline(self.config, self.search_dir)
            # Query recently indexed conversations from DuckDB
            cur = self._storage._read_cursor()
            rows = cur.execute(
                "SELECT conversation_id, project_id, full_text FROM conversations "
                "ORDER BY indexed_at DESC LIMIT 100"
            ).fetchall()

            if not rows:
                return

            batch = [
                {
                    "full_text": row[2],
                    "conversation_id": row[0],
                    "project_id": row[1],
                }
                for row in rows
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
