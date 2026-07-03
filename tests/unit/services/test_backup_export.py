from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from searchat.services.backup_export import (
    SOURCE_OF_TRUTH_TABLES,
    export_source_tables,
    import_source_tables,
)
from searchat.storage.unified_storage import UnifiedStorage


def _seed_unified_storage(db_path: Path) -> None:
    """Populate every Phase 1 table -- both source-of-truth and derived."""
    storage = UnifiedStorage(db_path)
    try:
        con = storage.connection
        con.execute(
            "INSERT INTO conversations "
            "(conversation_id, project_id, file_path, title, created_at, updated_at, "
            "message_count, full_text, file_hash, indexed_at) "
            "VALUES ('c1', 'p1', '/tmp/c1.jsonl', 'Conv 1', now(), now(), 1, 'hello world', 'h1', now())"
        )
        con.execute(
            "INSERT INTO messages (conversation_id, sequence, role, content) "
            "VALUES ('c1', 0, 'user', 'hello')"
        )
        con.execute(
            "INSERT INTO source_file_state (file_path, conversation_id, project_id, file_size, updated_at) "
            "VALUES ('/tmp/c1.jsonl', 'c1', 'p1', 42, now())"
        )
        con.execute(
            "INSERT INTO code_blocks "
            "(conversation_id, project_id, message_index, block_index, code, code_hash, lines) "
            "VALUES ('c1', 'p1', 0, 0, 'print(1)', 'ch1', 1)"
        )
        con.execute(
            "INSERT INTO exchanges (exchange_id, conversation_id, ply_start, ply_end, exchange_text, created_at) "
            "VALUES ('e1', 'c1', 0, 0, 'hello', now())"
        )
        con.execute(
            "INSERT INTO verbatim_embeddings (exchange_id, embedding) VALUES ('e1', ?)",
            [[0.1] * 384],
        )
    finally:
        storage.close()


@pytest.mark.unit
def test_export_source_tables_returns_empty_for_missing_database(tmp_path: Path) -> None:
    assert export_source_tables(tmp_path / "missing.duckdb", tmp_path / "export") == []


@pytest.mark.unit
def test_export_source_tables_writes_only_source_of_truth_parquet(tmp_path: Path) -> None:
    db_path = tmp_path / "searchat.duckdb"
    _seed_unified_storage(db_path)

    export_dir = tmp_path / "export"
    exported = export_source_tables(db_path, export_dir)

    assert sorted(exported) == sorted(SOURCE_OF_TRUTH_TABLES)
    for table in SOURCE_OF_TRUTH_TABLES:
        assert (export_dir / f"{table}.parquet").exists()
    # Derived tables never get exported.
    assert not (export_dir / "exchanges.parquet").exists()
    assert not (export_dir / "verbatim_embeddings.parquet").exists()

    con = duckdb.connect()
    try:
        row = con.execute(
            "SELECT conversation_id, title FROM read_parquet(?)",
            [str(export_dir / "conversations.parquet")],
        ).fetchone()
    finally:
        con.close()
    assert row == ("c1", "Conv 1")


@pytest.mark.unit
def test_export_source_tables_skips_absent_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "partial.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute("CREATE TABLE conversations(conversation_id VARCHAR)")
    con.execute("INSERT INTO conversations VALUES ('c1')")
    con.execute("CHECKPOINT")
    con.close()

    export_dir = tmp_path / "export"
    exported = export_source_tables(db_path, export_dir)

    assert exported == ["conversations"]
    assert (export_dir / "conversations.parquet").exists()
    assert not (export_dir / "messages.parquet").exists()


@pytest.mark.unit
def test_export_source_tables_does_not_mutate_source_database(tmp_path: Path) -> None:
    db_path = tmp_path / "searchat.duckdb"
    _seed_unified_storage(db_path)
    before = db_path.stat().st_mtime_ns

    export_source_tables(db_path, tmp_path / "export")

    assert db_path.stat().st_mtime_ns == before


@pytest.mark.unit
def test_import_source_tables_roundtrips_into_fresh_database_without_derived_data(tmp_path: Path) -> None:
    src_db = tmp_path / "searchat.duckdb"
    _seed_unified_storage(src_db)
    export_dir = tmp_path / "export"
    export_source_tables(src_db, export_dir)

    dest_db = tmp_path / "restored" / "searchat.duckdb"
    imported = import_source_tables(dest_db, export_dir)

    assert sorted(imported) == sorted(SOURCE_OF_TRUTH_TABLES)

    storage = UnifiedStorage(dest_db)
    try:
        con = storage.connection
        conv_row = con.execute("SELECT conversation_id, title FROM conversations").fetchone()
        assert conv_row == ("c1", "Conv 1")
        assert con.execute("SELECT count(*) FROM messages").fetchone()[0] == 1
        assert con.execute("SELECT count(*) FROM source_file_state").fetchone()[0] == 1
        assert con.execute("SELECT count(*) FROM code_blocks").fetchone()[0] == 1
        # Derived tables exist (schema created) but stay empty -- rebuild_derived's job.
        assert con.execute("SELECT count(*) FROM exchanges").fetchone()[0] == 0
        assert con.execute("SELECT count(*) FROM verbatim_embeddings").fetchone()[0] == 0
    finally:
        storage.close()


@pytest.mark.unit
def test_import_source_tables_refuses_existing_database(tmp_path: Path) -> None:
    dest_db = tmp_path / "searchat.duckdb"
    UnifiedStorage(dest_db).close()

    with pytest.raises(FileExistsError):
        import_source_tables(dest_db, tmp_path / "export")


@pytest.mark.unit
def test_import_source_tables_skips_absent_parquet_files(tmp_path: Path) -> None:
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    # No parquet files at all -- an empty/legacy-engine export.

    dest_db = tmp_path / "restored" / "searchat.duckdb"
    imported = import_source_tables(dest_db, export_dir)

    assert imported == []
    assert dest_db.exists()
