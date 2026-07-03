"""Selective DuckDB table export/import for source-of-truth-only backups.

`searchat.duckdb` (the unified engine's single storage file) mixes
source-of-truth tables (`conversations`, `messages`, `source_file_state`,
`code_blocks`) with derived tables (`exchanges`, `verbatim_embeddings`)
plus their FTS/HNSW indexes. A source-of-truth-only backup must not copy
that file wholesale -- doing so would either lose the source tables (if
excluded outright) or keep the bulk of the derivable index (if included).
This module exports just the source-of-truth tables to Parquet, and
re-imports them into a fresh database on restore, leaving `rebuild_derived`
(M2's `UnifiedIndexer.rebuild_derived`) to regenerate everything else.

Every connection loads the `vss`/`fts` extensions before running any query,
mirroring `services/compaction.py::_prepare_connection`: a DuckDB catalog
referencing an HNSW/FTS index FATALs the whole process on first use if the
owning extension isn't loaded yet, and a FATAL error cannot be caught by a
Python `except` clause.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

from searchat.storage.schema import install_fts, install_vss

SOURCE_OF_TRUTH_TABLES: tuple[str, ...] = (
    "conversations",
    "messages",
    "source_file_state",
    "code_blocks",
)


def _sql_literal(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def export_source_tables(db_path: Path, dest_dir: Path) -> list[str]:
    """Export each source-of-truth table found in `db_path` to Parquet.

    Read-only: never mutates `db_path`. Writes `dest_dir/<table>.parquet`
    for every table in `SOURCE_OF_TRUTH_TABLES` that actually exists in
    the database, skipping any that don't (an older or partial schema).

    Returns the list of table names actually exported. Returns `[]`
    without touching the filesystem when `db_path` doesn't exist.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return []

    con = duckdb.connect(str(db_path), read_only=True)
    exported: list[str] = []
    try:
        install_vss(con)
        install_fts(con)

        existing = {
            row[0]
            for row in con.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            ).fetchall()
        }

        dest_dir.mkdir(parents=True, exist_ok=True)
        for table in SOURCE_OF_TRUTH_TABLES:
            if table not in existing:
                continue
            dest_file = dest_dir / f"{table}.parquet"
            con.execute(
                f"COPY (SELECT * FROM {_quote_ident(table)}) "
                f"TO {_sql_literal(dest_file)} (FORMAT PARQUET)"
            )
            exported.append(table)
    finally:
        con.close()

    return exported


def import_source_tables(db_path: Path, source_dir: Path) -> list[str]:
    """Load exported source-of-truth Parquet files into a fresh database.

    Creates `db_path` (and the full Phase 1 schema, via `UnifiedStorage`)
    if it doesn't already exist. Refuses to run against an existing
    database -- restore always targets a clean file, never a merge, so a
    pre-existing file at `db_path` is a caller bug, not a state to repair.

    Returns the list of table names actually imported (a table absent
    from `source_dir` -- an older backup, or one exported before that
    table existed -- is skipped, not an error).
    """
    db_path = Path(db_path)
    if db_path.exists():
        raise FileExistsError(
            f"Refusing to import source tables into an existing database: {db_path}"
        )

    from searchat.storage.unified_storage import UnifiedStorage

    storage = UnifiedStorage(db_path)
    imported: list[str] = []
    try:
        con = storage.connection
        for table in SOURCE_OF_TRUTH_TABLES:
            src_file = Path(source_dir) / f"{table}.parquet"
            if not src_file.exists():
                continue
            con.execute(
                f"INSERT INTO {_quote_ident(table)} "
                f"SELECT * FROM read_parquet({_sql_literal(src_file)})"
            )
            imported.append(table)
    finally:
        storage.close()

    return imported
