"""Cross-connector near-duplicate conversation detection (M11).

Report-only: `find_near_duplicates` never merges, deletes, or otherwise
mutates a conversation -- it only reads `verbatim_embeddings` (the existing
HNSW-backed table, see `storage/schema.py`), `exchanges`, `conversations`,
and `source_file_state`, and returns similarity-ranked suggestions for a
human (or the M6 dashboard) to review. Every DB call in this module is a
SELECT; there is no INSERT/UPDATE/DELETE/MERGE/DROP anywhere here.

Detection approach: for each conversation, mean-pool the embeddings of its
own exchanges (already computed by the embedding pipeline and stored in
`verbatim_embeddings`) into one L2-normalized conversation-level vector,
then compare vectors pairwise across conversations ingested by two
DIFFERENT connectors -- same-connector pairs are out of scope per the
milestone ("cross-agent duplicate detection"). A pair whose cosine
similarity meets or exceeds `similarity_threshold` is reported as a
suggestion, most-similar first.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import numpy as np

from searchat.core.connectors.registry import detect_connector

# Fallback default for standalone/CLI callers of `find_near_duplicates` that
# don't thread a `Config` through. The M6 dashboard integration instead
# passes `config.dedup.similarity_threshold` (see `settings.default.toml`'s
# `[dedup] similarity_threshold`).
DEFAULT_SIMILARITY_THRESHOLD: float = 0.92


@dataclass(frozen=True)
class DuplicateSuggestion:
    """One cross-connector near-duplicate conversation pair -- reported,
    never acted on. `similarity` is a cosine similarity, in practice within
    [0.0, 1.0] for the non-negative sentence embeddings this project
    stores.
    """

    conversation_id_a: str
    connector_a: str
    title_a: str
    conversation_id_b: str
    connector_b: str
    title_b: str
    similarity: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "conversation_id_a": self.conversation_id_a,
            "connector_a": self.connector_a,
            "title_a": self.title_a,
            "conversation_id_b": self.conversation_id_b,
            "connector_b": self.connector_b,
            "title_b": self.title_b,
            "similarity": self.similarity,
        }


@dataclass(frozen=True)
class _ConversationVector:
    conversation_id: str
    connector: str
    title: str
    vector: np.ndarray  # L2-normalized, shape (embedding_dim,)


def _resolve_connector(connector_name: str | None, file_path: str) -> str:
    """`connector_name` when present; otherwise fall back to detecting it
    from the stored file path -- the same fallback
    `disk_accounting._group_indexed_rows` uses for rows written before
    `connector_name` was threaded through `source_file_state`.
    """
    if connector_name:
        return connector_name
    try:
        return detect_connector(Path(file_path)).name
    except ValueError:
        return "unknown"


def _fetch_conversation_vectors(
    connection: duckdb.DuckDBPyConnection,
) -> list[_ConversationVector]:
    """Mean-pool every conversation's exchange embeddings into one
    L2-normalized vector, paired with its connector and title. A
    conversation with no indexed exchanges (no embeddings yet) is excluded
    -- there is nothing to compare it against. Every statement here is a
    SELECT.
    """
    try:
        meta_rows = connection.execute(
            """
            SELECT
                c.conversation_id,
                c.title,
                c.file_path,
                any_value(sfs.connector_name) AS connector_name
            FROM conversations c
            LEFT JOIN source_file_state sfs ON sfs.conversation_id = c.conversation_id
            GROUP BY c.conversation_id, c.title, c.file_path
            """
        ).fetchall()
    except duckdb.Error:
        return []
    if not meta_rows:
        return []

    try:
        embedding_rows = connection.execute(
            """
            SELECT e.conversation_id, ve.embedding
            FROM exchanges e
            JOIN verbatim_embeddings ve ON ve.exchange_id = e.exchange_id
            """
        ).fetchall()
    except duckdb.Error:
        return []

    embeddings_by_conversation: dict[str, list[Any]] = {}
    for conversation_id, embedding in embedding_rows:
        embeddings_by_conversation.setdefault(conversation_id, []).append(embedding)

    vectors: list[_ConversationVector] = []
    for conversation_id, title, file_path, connector_name in meta_rows:
        raw_embeddings = embeddings_by_conversation.get(conversation_id)
        if not raw_embeddings:
            continue
        mean_vector = np.asarray(raw_embeddings, dtype=np.float64).mean(axis=0)
        norm = float(np.linalg.norm(mean_vector))
        if norm == 0.0:
            continue
        vectors.append(
            _ConversationVector(
                conversation_id=conversation_id,
                connector=_resolve_connector(connector_name, file_path),
                title=title,
                vector=mean_vector / norm,
            )
        )
    return vectors


def find_near_duplicates(
    db_path: Path,
    *,
    connection: duckdb.DuckDBPyConnection | None = None,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> tuple[DuplicateSuggestion, ...]:
    """Report-only cross-connector near-duplicate conversation suggestions.

    Every conversation ingested by connector A is compared against every
    conversation ingested by a DIFFERENT connector B; pairs whose mean
    exchange-embedding cosine similarity meets or exceeds
    `similarity_threshold` are returned, most-similar first. Same-connector
    pairs are never compared -- this milestone is cross-agent duplicate
    detection specifically, not general within-connector dedup.

    Never merges, deletes, or writes anything: `_fetch_conversation_vectors`
    issues only SELECT statements, and the pairwise comparison below is pure
    in-memory numpy. `connection`: pass the live server's own open
    connection when available (mirrors
    `disk_accounting._read_indexed_paths_by_connector`) -- DuckDB refuses a
    second same-process connection to a file already opened with
    non-default config. When `connection` is not given (CLI/standalone
    use), a short-lived READ-ONLY connection to `db_path` is opened instead
    -- `read_only=True` additionally makes any accidental mutation
    impossible at the DB layer for that path, on top of this module never
    issuing one. Returns an empty tuple if `db_path` doesn't exist yet.
    """
    if connection is not None:
        vectors = _fetch_conversation_vectors(connection)
    else:
        if not db_path.exists():
            return ()
        own_connection = duckdb.connect(str(db_path), read_only=True)
        try:
            vectors = _fetch_conversation_vectors(own_connection)
        finally:
            own_connection.close()

    suggestions: list[DuplicateSuggestion] = []
    for i in range(len(vectors)):
        vector_a = vectors[i]
        for j in range(i + 1, len(vectors)):
            vector_b = vectors[j]
            if vector_a.connector == vector_b.connector:
                continue
            similarity = float(np.dot(vector_a.vector, vector_b.vector))
            if similarity >= similarity_threshold:
                suggestions.append(
                    DuplicateSuggestion(
                        conversation_id_a=vector_a.conversation_id,
                        connector_a=vector_a.connector,
                        title_a=vector_a.title,
                        conversation_id_b=vector_b.conversation_id,
                        connector_b=vector_b.connector,
                        title_b=vector_b.title,
                        similarity=similarity,
                    )
                )

    suggestions.sort(key=lambda s: (-s.similarity, s.conversation_id_a, s.conversation_id_b))
    return tuple(suggestions)
