from __future__ import annotations

import shutil

from pathlib import Path

import pytest

from searchat.services.backup import BackupManager


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _seed_duckdb_conversation(db_path: Path) -> None:
    """Create a minimal, schema-valid unified DuckDB with one conversation."""
    from searchat.storage.unified_storage import UnifiedStorage

    storage = UnifiedStorage(db_path)
    try:
        storage.connection.execute(
            "INSERT INTO conversations "
            "(conversation_id, project_id, file_path, title, created_at, updated_at, "
            "message_count, full_text, file_hash, indexed_at) "
            "VALUES ('c1', 'p1', '/tmp/c1.jsonl', 'Conv 1', now(), now(), 1, 'hello world', 'h1', now())"
        )
    finally:
        storage.close()


@pytest.mark.unit
def test_restore_imports_source_tables_and_invokes_rebuild_derived(temp_search_dir: Path) -> None:
    live = temp_search_dir
    mgr = BackupManager(live)

    _write_bytes(live / "data" / "conversations" / "conv.parquet", b"PAR1\n")
    _seed_duckdb_conversation(live / "data" / "searchat.duckdb")

    meta = mgr.create_backup(backup_name="snap")
    assert meta.excludes_derived is True

    # Break the live dataset so restore has something to rebuild.
    shutil.rmtree(live / "data")

    calls: list[Path] = []

    def _fake_rebuild(search_dir: Path) -> None:
        calls.append(search_dir)

    mgr.restore_from_backup(
        meta.backup_path,
        create_pre_restore_backup=False,
        rebuild_derived=_fake_rebuild,
    )

    assert calls == [live]
    assert (live / "data" / "searchat.duckdb").exists()
    assert not (live / "data" / "duckdb_source").exists()

    from searchat.storage.unified_storage import UnifiedStorage

    storage = UnifiedStorage(live / "data" / "searchat.duckdb", read_only=True)
    try:
        row = storage.connection.execute(
            "SELECT conversation_id, title FROM conversations"
        ).fetchone()
    finally:
        storage.close()
    assert row == ("c1", "Conv 1")


@pytest.mark.unit
def test_restore_skips_rebuild_when_no_duckdb_was_ever_exported(temp_search_dir: Path) -> None:
    live = temp_search_dir
    mgr = BackupManager(live)

    _write_bytes(live / "data" / "conversations" / "conv.parquet", b"PAR1\n")
    meta = mgr.create_backup(backup_name="snap")
    assert meta.excludes_derived is True

    calls: list[Path] = []
    mgr.restore_from_backup(
        meta.backup_path,
        create_pre_restore_backup=False,
        rebuild_derived=lambda search_dir: calls.append(search_dir),
    )

    assert calls == []
    assert not (live / "data" / "searchat.duckdb").exists()


@pytest.mark.unit
def test_restore_skips_rebuild_for_pre_m4_full_backup(temp_search_dir: Path) -> None:
    live = temp_search_dir
    mgr = BackupManager(live)

    _write_bytes(live / "data" / "conversations" / "conv.parquet", b"PAR1\n")
    _seed_duckdb_conversation(live / "data" / "searchat.duckdb")

    meta = mgr.create_backup(backup_name="full", excludes_derived=False, compressed=False)
    assert meta.excludes_derived is False

    calls: list[Path] = []
    mgr.restore_from_backup(
        meta.backup_path,
        create_pre_restore_backup=False,
        rebuild_derived=lambda search_dir: calls.append(search_dir),
    )

    assert calls == []
    # A pre-M4-style full backup restores searchat.duckdb byte-for-byte -- no
    # rebuild needed or triggered.
    assert (live / "data" / "searchat.duckdb").exists()


@pytest.mark.unit
def test_restore_defaults_excludes_derived_false_for_legacy_metadata_missing_field(
    temp_search_dir: Path,
) -> None:
    import json

    live = temp_search_dir
    mgr = BackupManager(live)

    _write_bytes(live / "data" / "conversations" / "conv.parquet", b"PAR1\n")
    _seed_duckdb_conversation(live / "data" / "searchat.duckdb")
    meta = mgr.create_backup(backup_name="snap")

    # Simulate a pre-M4 metadata file: strip the new field entirely.
    metadata_path = meta.backup_path / mgr.METADATA_FILE
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    payload.pop("excludes_derived", None)
    payload.pop("derived_schema_version", None)
    metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    calls: list[Path] = []
    mgr.restore_from_backup(
        meta.backup_path,
        create_pre_restore_backup=False,
        rebuild_derived=lambda search_dir: calls.append(search_dir),
    )

    assert calls == []


@pytest.mark.unit
def test_restore_default_rebuild_derived_constructs_real_unified_indexer(
    temp_search_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When no callback is injected, the default wires up the real
    UnifiedIndexer.rebuild_derived -- verified via a patch rather than
    actually running embeddings."""
    live = temp_search_dir
    mgr = BackupManager(live)

    _write_bytes(live / "data" / "conversations" / "conv.parquet", b"PAR1\n")
    _seed_duckdb_conversation(live / "data" / "searchat.duckdb")
    meta = mgr.create_backup(backup_name="snap")

    shutil.rmtree(live / "data")

    calls: list[tuple[Path, bool]] = []

    from searchat.core.unified_indexer import UnifiedIndexer

    def _fake_rebuild_derived(self: UnifiedIndexer, force: bool = False, progress=None):
        calls.append((self.search_dir, force))

    monkeypatch.setattr(UnifiedIndexer, "rebuild_derived", _fake_rebuild_derived)

    mgr.restore_from_backup(meta.backup_path, create_pre_restore_backup=False)

    assert calls == [(live, True)]


@pytest.mark.unit
def test_restore_into_empty_sandbox_yields_working_hybrid_and_keyword_search(
    temp_search_dir: Path,
) -> None:
    """End-to-end acceptance check: backup -> wipe -> restore -> automatic
    rebuild -> both FTS keyword search and HNSW vector search work against
    the restored data, matching M4's stated restore acceptance criterion."""
    import hashlib
    from datetime import datetime
    from unittest.mock import MagicMock, patch

    import numpy as np

    from searchat.config import Config
    from searchat.core.unified_indexer import UnifiedIndexer
    from searchat.storage.unified_storage import UnifiedStorage

    def _deterministic_vector(text: str) -> list[float]:
        seed = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        return rng.random(384).tolist()

    def _fake_embedder() -> MagicMock:
        embedder = MagicMock()
        embedder.encode.side_effect = lambda batch, **kwargs: np.array(
            [_deterministic_vector(text) for text in batch]
        )
        return embedder

    live = temp_search_dir
    db_path = live / "data" / "searchat.duckdb"

    now = datetime(2026, 1, 1, 12, 0, 0)
    storage = UnifiedStorage(db_path)
    storage.upsert_conversation(
        conversation_id="conv-a",
        project_id="proj1",
        file_path="/fake/does/not/exist/conv-a.jsonl",
        title="Conversation conv-a",
        created_at=now,
        updated_at=now,
        message_count=4,
        full_text="hello world",
        file_hash="hash-conv-a",
        indexed_at=now,
    )
    storage.insert_messages(
        "conv-a",
        [
            {
                "sequence": i,
                "role": "user" if i % 2 == 0 else "assistant",
                "content": f"conv-a message {i} about sorting a python list quickly",
                "timestamp": now,
                "has_code": False,
                "code_blocks": None,
            }
            for i in range(4)
        ],
    )
    storage.close()

    config = Config.load()
    with patch.object(UnifiedIndexer, "_get_embedder", return_value=_fake_embedder()):
        UnifiedIndexer(live, config).rebuild_derived(force=True)

    mgr = BackupManager(live)
    backup = mgr.create_backup(backup_name="snap")
    assert backup.excludes_derived is True

    # Simulate restoring into an empty sandbox SEARCHAT_HOME.
    shutil.rmtree(live / "data")

    with patch.object(UnifiedIndexer, "_get_embedder", return_value=_fake_embedder()):
        result = mgr.restore_from_backup(backup.backup_path, create_pre_restore_backup=False)

    assert result.rebuild_performed is True

    restored = UnifiedStorage(db_path, read_only=True)
    try:
        con = restored.connection
        assert con.execute("SELECT count(*) FROM conversations").fetchone()[0] == 1
        assert con.execute("SELECT count(*) FROM exchanges").fetchone()[0] > 0
        assert con.execute("SELECT count(*) FROM verbatim_embeddings").fetchone()[0] > 0

        # Keyword search: FTS BM25 finds the seeded exchange by a real word.
        keyword_hits = con.execute(
            "SELECT exchange_id, fts_main_exchanges.match_bm25(exchange_id, 'sorting') AS score "
            "FROM exchanges WHERE score IS NOT NULL"
        ).fetchall()
        assert keyword_hits, "expected FTS to find the seeded 'sorting' exchange after restore"

        # Semantic search: HNSW-backed cosine similarity returns neighbors.
        probe = con.execute(
            "SELECT embedding FROM verbatim_embeddings ORDER BY exchange_id LIMIT 1"
        ).fetchone()
        neighbors = con.execute(
            "SELECT exchange_id, array_cosine_distance(embedding, ?::FLOAT[384]) AS dist "
            "FROM verbatim_embeddings ORDER BY dist LIMIT 5",
            [probe[0]],
        ).fetchall()
        assert neighbors, "expected HNSW vector search to return neighbors after restore"
    finally:
        restored.close()

