"""One-time ETL migration: Parquet+FAISS (v1) → DuckDB (v2).

Reads existing index data from ~/.searchat/data/ and populates all
DuckDB tables. NEVER deletes or modifies original Parquet/FAISS files.

Usage via CLI:
    searchat migrate-storage --dry-run    # scan + estimate
    searchat migrate-storage              # perform ETL
    searchat migrate-storage --verify     # row counts + sample diffs
"""
from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pyarrow.parquet as pq

from searchat.storage.unified_storage import UnifiedStorage

log = logging.getLogger(__name__)


@dataclass
class MigrationStats:
    conversations: int = 0
    messages: int = 0
    exchanges: int = 0
    embeddings: int = 0
    file_states: int = 0
    code_blocks: int = 0
    elapsed_seconds: float = 0.0
    errors: list[str] | None = None

    def to_dict(self) -> dict:
        return {
            "conversations": self.conversations,
            "messages": self.messages,
            "exchanges": self.exchanges,
            "embeddings": self.embeddings,
            "file_states": self.file_states,
            "code_blocks": self.code_blocks,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "errors": self.errors or [],
        }


@dataclass
class DryRunReport:
    conversation_parquets: int = 0
    total_conversations: int = 0
    estimated_messages: int = 0
    embeddings_metadata_rows: int = 0
    faiss_vectors: int = 0
    file_state_rows: int = 0
    code_parquets: int = 0
    code_block_rows: int = 0
    duckdb_path: str = ""

    def to_dict(self) -> dict:
        return {
            "conversation_parquets": self.conversation_parquets,
            "total_conversations": self.total_conversations,
            "estimated_messages": self.estimated_messages,
            "embeddings_metadata_rows": self.embeddings_metadata_rows,
            "faiss_vectors": self.faiss_vectors,
            "file_state_rows": self.file_state_rows,
            "code_parquets": self.code_parquets,
            "code_block_rows": self.code_block_rows,
            "duckdb_path": self.duckdb_path,
        }


def dry_run(search_dir: Path, duckdb_path: Path) -> DryRunReport:
    """Scan existing v1 data and estimate migration scope."""
    data_dir = search_dir / "data"
    report = DryRunReport(duckdb_path=str(duckdb_path))

    # Conversation parquets
    conv_dir = data_dir / "conversations"
    if conv_dir.exists():
        parquets = sorted(conv_dir.glob("*.parquet"))
        report.conversation_parquets = len(parquets)
        for pf in parquets:
            table = pq.read_table(pf, columns=["conversation_id", "message_count"])
            report.total_conversations += len(table)
            report.estimated_messages += table.column("message_count").to_pylist().__iter__().__class__(
                sum(table.column("message_count").to_pylist())
            ) if False else sum(table.column("message_count").to_pylist())

    # Embeddings metadata
    emb_meta = data_dir / "indices" / "embeddings.metadata.parquet"
    if emb_meta.exists():
        table = pq.read_metadata(emb_meta)
        report.embeddings_metadata_rows = table.num_rows

    # FAISS index
    faiss_path = data_dir / "indices" / "embeddings.faiss"
    if faiss_path.exists():
        try:
            import faiss
            index = faiss.read_index(str(faiss_path))
            report.faiss_vectors = index.ntotal
        except Exception as exc:
            log.warning("Cannot read FAISS index: %s", exc)

    # File state
    fs_path = data_dir / "indices" / "file_state.parquet"
    if fs_path.exists():
        report.file_state_rows = pq.read_metadata(fs_path).num_rows

    # Code blocks
    code_dir = data_dir / "code"
    if code_dir.exists():
        code_parquets = sorted(code_dir.glob("*.parquet"))
        report.code_parquets = len(code_parquets)
        for pf in code_parquets:
            report.code_block_rows += pq.read_metadata(pf).num_rows

    return report


def migrate(
    search_dir: Path,
    duckdb_path: Path,
    *,
    memory_limit_mb: int | None = None,
) -> MigrationStats:
    """Perform the full v1 → v2 migration.

    NEVER deletes or modifies existing Parquet/FAISS files.
    """
    start = time.monotonic()
    stats = MigrationStats(errors=[])
    data_dir = search_dir / "data"

    storage = UnifiedStorage(duckdb_path, memory_limit_mb=memory_limit_mb)

    try:
        stats.conversations, stats.messages, stats.exchanges = _migrate_conversations(
            data_dir / "conversations", storage
        )
        stats.embeddings = _migrate_embeddings(data_dir / "indices", storage)
        stats.file_states = _migrate_file_state(data_dir / "indices", storage)
        stats.code_blocks = _migrate_code_blocks(data_dir / "code", storage)
    except Exception as exc:
        log.exception("Migration failed")
        stats.errors.append(str(exc))  # type: ignore[union-attr]
    finally:
        stats.elapsed_seconds = time.monotonic() - start
        storage.close()

    return stats


def _migrate_conversations(
    conv_dir: Path,
    storage: UnifiedStorage,
) -> tuple[int, int, int]:
    """Migrate conversation parquets → conversations + messages + exchanges."""
    if not conv_dir.exists():
        return 0, 0, 0

    total_convs = 0
    total_msgs = 0
    total_exchanges = 0

    for pf in sorted(conv_dir.glob("*.parquet")):
        table = pq.read_table(pf)
        for i in range(len(table)):
            row = {col: table.column(col)[i].as_py() for col in table.column_names}

            conv_id = row["conversation_id"]
            project_id = row["project_id"]
            created_at = row.get("created_at") or datetime.now()
            updated_at = row.get("updated_at") or created_at

            storage.upsert_conversation(
                conversation_id=conv_id,
                project_id=project_id,
                file_path=row.get("file_path", ""),
                title=row.get("title", ""),
                created_at=created_at,
                updated_at=updated_at,
                message_count=row.get("message_count", 0),
                full_text=row.get("full_text", ""),
                file_hash=row.get("file_hash", ""),
                indexed_at=row.get("indexed_at") or datetime.now(),
                files_mentioned=row.get("files_mentioned"),
                git_branch=row.get("git_branch"),
            )
            total_convs += 1

            # Messages (nested list<struct>)
            messages_raw = row.get("messages") or []
            msg_dicts = []
            for msg in messages_raw:
                msg_dicts.append({
                    "sequence": msg.get("sequence", 0),
                    "role": msg.get("role", "unknown"),
                    "content": msg.get("content", ""),
                    "timestamp": msg.get("timestamp"),
                    "has_code": msg.get("has_code", False),
                    "code_blocks": msg.get("code_blocks"),
                })
            if msg_dicts:
                storage.insert_messages(conv_id, msg_dicts)
                total_msgs += len(msg_dicts)

            # Derive exchanges from message pairs
            exchanges = _derive_exchanges(conv_id, project_id, msg_dicts, created_at)
            for exc in exchanges:
                storage.upsert_exchange(**exc)
                total_exchanges += 1

        log.info("Migrated %s: %d conversations", pf.name, len(table))

    return total_convs, total_msgs, total_exchanges


def _derive_exchanges(
    conversation_id: str,
    project_id: str,
    messages: list[dict],
    fallback_time: datetime,
) -> list[dict]:
    """Derive exchange segments from a flat message list.

    An exchange starts at each 'user' message and spans through
    the subsequent 'assistant' messages until the next 'user' or
    end of conversation.
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
            # Close previous exchange
            if current_start is not None and current_texts:
                ply_end = seq - 1
                _append_exchange(
                    exchanges, conversation_id, project_id,
                    current_start, ply_end, current_texts, fallback_time,
                )
            current_start = seq
            current_texts = [msg["content"]]
        else:
            if current_start is None:
                current_start = seq
                current_texts = []
            current_texts.append(msg["content"])

    # Close final exchange
    if current_start is not None and current_texts:
        ply_end = messages[-1]["sequence"]
        _append_exchange(
            exchanges, conversation_id, project_id,
            current_start, ply_end, current_texts, fallback_time,
        )

    return exchanges


def _append_exchange(
    exchanges: list[dict],
    conversation_id: str,
    project_id: str,
    ply_start: int,
    ply_end: int,
    texts: list[str],
    fallback_time: datetime,
) -> None:
    exchange_text = "\n\n".join(texts)
    exchange_id = hashlib.sha256(
        f"{conversation_id}:{ply_start}:{ply_end}".encode()
    ).hexdigest()[:16]
    exchanges.append({
        "exchange_id": exchange_id,
        "conversation_id": conversation_id,
        "project_id": project_id,
        "ply_start": ply_start,
        "ply_end": ply_end,
        "exchange_text": exchange_text,
        "created_at": fallback_time,
    })


def _migrate_embeddings(
    indices_dir: Path,
    storage: UnifiedStorage,
) -> int:
    """Migrate FAISS vectors + metadata → verbatim_embeddings.

    Maps v1 chunk-based embeddings to exchange IDs by matching
    conversation_id + message range to the exchange table.
    """
    emb_meta_path = indices_dir / "embeddings.metadata.parquet"
    faiss_path = indices_dir / "embeddings.faiss"

    if not emb_meta_path.exists():
        log.info("No embeddings metadata found, skipping")
        return 0

    meta_table = pq.read_table(emb_meta_path)
    log.info("Embeddings metadata: %d rows", len(meta_table))

    # Load FAISS vectors if available
    vectors = None
    if faiss_path.exists():
        try:
            import faiss
            index = faiss.read_index(str(faiss_path))
            if index.ntotal > 0:
                vectors = faiss.rev_swig_ptr(
                    index.reconstruct_n(0, index.ntotal),
                    index.ntotal * index.d,
                ).reshape(index.ntotal, index.d).copy()
                log.info("FAISS vectors loaded: %d x %d", *vectors.shape)
        except Exception as exc:
            log.warning("Cannot load FAISS vectors: %s", exc)

    count = 0
    for i in range(len(meta_table)):
        row = {col: meta_table.column(col)[i].as_py() for col in meta_table.column_names}
        vector_id = row.get("vector_id", i)

        conv_id = row["conversation_id"]
        msg_start = row.get("message_start_index", 0)
        msg_end = row.get("message_end_index", msg_start)

        # Generate exchange_id matching the derivation logic
        exchange_id = hashlib.sha256(
            f"{conv_id}:{msg_start}:{msg_end}".encode()
        ).hexdigest()[:16]

        if vectors is not None and vector_id < len(vectors):
            embedding = vectors[vector_id].tolist()
            storage.upsert_embedding(exchange_id, embedding)
            count += 1

    log.info("Migrated %d embeddings", count)
    return count


def _migrate_file_state(
    indices_dir: Path,
    storage: UnifiedStorage,
) -> int:
    """Migrate file_state.parquet → source_file_state."""
    fs_path = indices_dir / "file_state.parquet"
    if not fs_path.exists():
        return 0

    table = pq.read_table(fs_path)
    count = 0
    for i in range(len(table)):
        row = {col: table.column(col)[i].as_py() for col in table.column_names}
        storage.upsert_file_state(
            file_path=row["file_path"],
            conversation_id=row.get("conversation_id"),
            project_id=row.get("project_id"),
            connector_name=row.get("connector_name"),
            file_size=row.get("file_size", 0),
            file_hash=row.get("file_hash"),
            updated_at=row.get("indexed_at") or datetime.now(),
        )
        count += 1

    log.info("Migrated %d file state records", count)
    return count


def _migrate_code_blocks(
    code_dir: Path,
    storage: UnifiedStorage,
) -> int:
    """Migrate code block parquets → code_blocks table."""
    if not code_dir.exists():
        return 0

    count = 0
    for pf in sorted(code_dir.glob("*.parquet")):
        table = pq.read_table(pf)
        for i in range(len(table)):
            row = {col: table.column(col)[i].as_py() for col in table.column_names}
            storage.insert_code_block(
                conversation_id=row["conversation_id"],
                project_id=row["project_id"],
                connector=row.get("connector"),
                file_path=row.get("file_path"),
                title=row.get("title"),
                conversation_created_at=row.get("conversation_created_at"),
                conversation_updated_at=row.get("conversation_updated_at"),
                message_index=row["message_index"],
                block_index=row["block_index"],
                role=row.get("role"),
                message_timestamp=row.get("message_timestamp"),
                fence_language=row.get("fence_language"),
                language=row.get("language"),
                language_source=row.get("language_source"),
                functions=row.get("functions"),
                classes=row.get("classes"),
                imports=row.get("imports"),
                code=row["code"],
                code_hash=row["code_hash"],
                lines=row["lines"],
            )
            count += 1

        log.info("Migrated %s: %d code blocks", pf.name, len(table))

    return count


def verify(search_dir: Path, duckdb_path: Path) -> dict:
    """Compare row counts between v1 (Parquet) and v2 (DuckDB)."""
    data_dir = search_dir / "data"
    result: dict[str, dict[str, int]] = {}

    # Conversation counts
    conv_dir = data_dir / "conversations"
    v1_convs = 0
    v1_msgs = 0
    if conv_dir.exists():
        for pf in conv_dir.glob("*.parquet"):
            table = pq.read_table(pf, columns=["conversation_id", "message_count"])
            v1_convs += len(table)
            v1_msgs += sum(table.column("message_count").to_pylist())

    # File state
    v1_fs = 0
    fs_path = data_dir / "indices" / "file_state.parquet"
    if fs_path.exists():
        v1_fs = pq.read_metadata(fs_path).num_rows

    # Code blocks
    v1_code = 0
    code_dir = data_dir / "code"
    if code_dir.exists():
        for pf in code_dir.glob("*.parquet"):
            v1_code += pq.read_metadata(pf).num_rows

    # DuckDB counts
    storage = UnifiedStorage(duckdb_path, read_only=True)
    try:
        v2 = storage.get_row_counts()
    finally:
        storage.close()

    result["conversations"] = {"v1": v1_convs, "v2": v2.get("conversations", 0)}
    result["messages"] = {"v1": v1_msgs, "v2": v2.get("messages", 0)}
    result["exchanges"] = {"v1": 0, "v2": v2.get("exchanges", 0)}  # no v1 equivalent
    result["verbatim_embeddings"] = {"v1": 0, "v2": v2.get("verbatim_embeddings", 0)}
    result["source_file_state"] = {"v1": v1_fs, "v2": v2.get("source_file_state", 0)}
    result["code_blocks"] = {"v1": v1_code, "v2": v2.get("code_blocks", 0)}

    return result
