"""DuckDB schema definitions — DDL, migrations, and index creation.

Tables for Phase 1 (core storage):
  conversations, messages, exchanges, verbatim_embeddings,
  source_file_state, code_blocks

Palace tables (palace_objects, rooms, room_objects, facet_embeddings,
hierarchical_facets) are deferred to Phase 6.
"""
from __future__ import annotations

import logging

import duckdb

log = logging.getLogger(__name__)

EMBEDDING_DIM: int = 384


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

_CORE_DDL = f"""\
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id VARCHAR PRIMARY KEY,
    project_id      VARCHAR NOT NULL,
    file_path       VARCHAR NOT NULL,
    title           VARCHAR NOT NULL,
    created_at      TIMESTAMP NOT NULL,
    updated_at      TIMESTAMP NOT NULL,
    message_count   INTEGER NOT NULL,
    full_text       TEXT NOT NULL,
    file_hash       VARCHAR NOT NULL,
    indexed_at      TIMESTAMP NOT NULL,
    file_size       BIGINT DEFAULT 0,
    mtime_ns        BIGINT DEFAULT 0,
    files_mentioned JSON,
    git_branch      VARCHAR
);

CREATE TABLE IF NOT EXISTS messages (
    conversation_id VARCHAR NOT NULL,
    sequence        INTEGER NOT NULL,
    role            VARCHAR NOT NULL,
    content         TEXT NOT NULL,
    timestamp       TIMESTAMP,
    has_code        BOOLEAN DEFAULT FALSE,
    code_blocks     JSON,
    PRIMARY KEY (conversation_id, sequence)
);

CREATE TABLE IF NOT EXISTS exchanges (
    exchange_id     VARCHAR PRIMARY KEY,
    conversation_id VARCHAR NOT NULL,
    project_id      VARCHAR,
    ply_start       INTEGER NOT NULL,
    ply_end         INTEGER NOT NULL,
    exchange_text   TEXT NOT NULL,
    created_at      TIMESTAMP NOT NULL,
    UNIQUE(conversation_id, ply_start, ply_end)
);

CREATE TABLE IF NOT EXISTS verbatim_embeddings (
    exchange_id VARCHAR PRIMARY KEY,
    embedding   FLOAT[{EMBEDDING_DIM}] NOT NULL
);

CREATE TABLE IF NOT EXISTS source_file_state (
    file_path       VARCHAR PRIMARY KEY,
    conversation_id VARCHAR,
    project_id      VARCHAR,
    connector_name  VARCHAR,
    status          VARCHAR NOT NULL DEFAULT 'indexed',
    file_size       BIGINT NOT NULL,
    file_hash       VARCHAR,
    mtime_ns        BIGINT DEFAULT 0,
    error_message   TEXT,
    updated_at      TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS code_blocks (
    conversation_id         VARCHAR NOT NULL,
    project_id              VARCHAR NOT NULL,
    connector               VARCHAR,
    file_path               VARCHAR,
    title                   VARCHAR,
    conversation_created_at TIMESTAMP,
    conversation_updated_at TIMESTAMP,
    message_index           INTEGER NOT NULL,
    block_index             INTEGER NOT NULL,
    role                    VARCHAR,
    message_timestamp       TIMESTAMP,
    fence_language          VARCHAR,
    language                VARCHAR,
    language_source         VARCHAR,
    functions               JSON,
    classes                 JSON,
    imports                 JSON,
    code                    TEXT NOT NULL,
    code_hash               VARCHAR NOT NULL,
    lines                   INTEGER NOT NULL,
    PRIMARY KEY (conversation_id, message_index, block_index)
);
"""

# Scalar indexes for common query patterns
_SCALAR_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_conv_project ON conversations(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_conv_updated ON conversations(updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id)",
    "CREATE INDEX IF NOT EXISTS idx_exch_conv ON exchanges(conversation_id)",
    "CREATE INDEX IF NOT EXISTS idx_code_conv ON code_blocks(conversation_id)",
    "CREATE INDEX IF NOT EXISTS idx_sfs_conv ON source_file_state(conversation_id)",
]


def ensure_tables(conn: duckdb.DuckDBPyConnection) -> None:
    """Create all Phase 1 tables if they don't exist, then run migrations."""
    conn.execute(_CORE_DDL)
    for idx_ddl in _SCALAR_INDEXES:
        conn.execute(idx_ddl)
    _run_migrations(conn)


def _run_migrations(conn: duckdb.DuckDBPyConnection) -> None:
    """Idempotent ALTER TABLE migrations for forward compatibility."""
    # Future migrations go here using ADD COLUMN IF NOT EXISTS


# ---------------------------------------------------------------------------
# VSS (HNSW) indexes
# ---------------------------------------------------------------------------

def install_vss(conn: duckdb.DuckDBPyConnection) -> bool:
    """Install and load the VSS extension. Returns True on success."""
    try:
        conn.execute("INSTALL vss")
        conn.execute("LOAD vss")
        log.info("DuckDB VSS extension loaded")
        return True
    except duckdb.Error as exc:
        log.warning("VSS extension unavailable: %s", exc)
        return False


def create_hnsw_indexes(
    conn: duckdb.DuckDBPyConnection,
    *,
    ef_construction: int = 128,
    m: int = 16,
) -> None:
    """Create HNSW indexes on embedding columns.

    Only creates indexes that don't already exist. Failures are logged,
    not raised — missing HNSW degrades to sequential scan.
    """
    existing = {
        row[0]
        for row in conn.execute(
            "SELECT index_name FROM duckdb_indexes() "
            "WHERE index_name IN ('verbatim_hnsw')"
        ).fetchall()
    }

    indexes = [
        (
            "verbatim_hnsw",
            f"CREATE INDEX verbatim_hnsw ON verbatim_embeddings "
            f"USING HNSW (embedding) WITH (metric = 'cosine', "
            f"ef_construction = {ef_construction}, M = {m})",
        ),
    ]

    for name, ddl in indexes:
        if name in existing:
            continue
        try:
            conn.execute(ddl)
            log.info("Created HNSW index %s", name)
        except duckdb.Error as exc:
            log.warning("Failed to create HNSW index %s: %s", name, exc)


# ---------------------------------------------------------------------------
# FTS indexes
# ---------------------------------------------------------------------------

def install_fts(conn: duckdb.DuckDBPyConnection) -> bool:
    """Install and load the FTS extension. Returns True on success."""
    try:
        conn.execute("INSTALL fts")
        conn.execute("LOAD fts")
        log.info("DuckDB FTS extension loaded")
        return True
    except duckdb.Error as exc:
        log.warning("FTS extension unavailable: %s", exc)
        return False


def create_fts_indexes(conn: duckdb.DuckDBPyConnection) -> None:
    """Create FTS indexes on exchange_text for BM25 keyword search."""
    try:
        conn.execute(
            "PRAGMA create_fts_index("
            "'exchanges', 'exchange_id', 'exchange_text', "
            "stemmer = 'porter', stopwords = 'english', overwrite = 1"
            ")"
        )
        log.info("Created FTS index on exchanges.exchange_text")
    except duckdb.Error as exc:
        log.warning("Failed to create FTS index on exchanges: %s", exc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def table_row_counts(conn: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Return row counts for all Phase 1 tables."""
    tables = [
        "conversations", "messages", "exchanges",
        "verbatim_embeddings", "source_file_state", "code_blocks",
    ]
    counts: dict[str, int] = {}
    for table in tables:
        try:
            row = conn.execute(f"SELECT count(*) FROM {table}").fetchone()  # noqa: S608
            counts[table] = row[0] if row else 0
        except duckdb.Error:
            counts[table] = 0
    return counts
