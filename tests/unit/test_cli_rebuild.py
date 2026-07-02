"""Unit tests for `searchat rebuild-derived` / `searchat reingest-sources` CLI commands."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from searchat.config import Config
from searchat.core.unified_indexer import UnifiedIndexer
from searchat.models import IndexStats
from searchat.storage.unified_storage import UnifiedStorage


def _db_path(search_dir: Path) -> Path:
    return search_dir / "data" / "searchat.duckdb"


def _seed_conversation(storage: UnifiedStorage, conversation_id: str, *, n_messages: int = 4) -> None:
    """Populate conversations/messages directly — never via a connector/file."""
    now = datetime(2026, 1, 1, 12, 0, 0)
    storage.upsert_conversation(
        conversation_id=conversation_id,
        project_id="proj1",
        file_path=f"/fake/does/not/exist/{conversation_id}.jsonl",
        title=f"Conversation {conversation_id}",
        created_at=now,
        updated_at=now,
        message_count=n_messages,
        full_text="hello world",
        file_hash=f"hash-{conversation_id}",
        indexed_at=now,
    )
    messages = [
        {
            "sequence": i,
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"{conversation_id} message {i} about sorting a python list",
            "timestamp": now,
            "has_code": False,
            "code_blocks": None,
        }
        for i in range(n_messages)
    ]
    storage.insert_messages(conversation_id, messages)


def _deterministic_vector(text: str) -> list[float]:
    """Same text -> same 384-dim vector, every time."""
    seed = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    return rng.random(384).tolist()


def _fake_embedder() -> MagicMock:
    """Deterministic stand-in for SentenceTransformer — avoids loading a real model."""
    embedder = MagicMock()
    embedder.encode.side_effect = lambda batch, **kwargs: np.array(
        [_deterministic_vector(text) for text in batch]
    )
    return embedder


def _seed_two_conversations(temp_search_dir: Path) -> None:
    storage = UnifiedStorage(_db_path(temp_search_dir))
    _seed_conversation(storage, "conv-a")
    _seed_conversation(storage, "conv-b")
    storage.close()


# ---------------------------------------------------------------------------
# --help
# ---------------------------------------------------------------------------

def test_rebuild_derived_help_text(capsys) -> None:
    from searchat.cli.rebuild_cmd import run_rebuild_derived

    with pytest.raises(SystemExit) as exc_info:
        run_rebuild_derived(["--help"])
    assert exc_info.value.code == 0

    captured = capsys.readouterr()
    assert "rebuild-derived" in captured.out
    assert "--force" in captured.out
    assert "--json" in captured.out


def test_reingest_sources_help_text(capsys) -> None:
    from searchat.cli.rebuild_cmd import run_reingest_sources

    with pytest.raises(SystemExit) as exc_info:
        run_reingest_sources(["--help"])
    assert exc_info.value.code == 0

    captured = capsys.readouterr()
    assert "reingest-sources" in captured.out
    assert "--force" in captured.out


# ---------------------------------------------------------------------------
# rebuild-derived: success paths
# ---------------------------------------------------------------------------

def test_rebuild_derived_summary_output(temp_search_dir: Path, capsys) -> None:
    from searchat.cli.rebuild_cmd import run_rebuild_derived

    _seed_two_conversations(temp_search_dir)
    config = Config.load()

    with (
        patch("searchat.config.Config.load", return_value=config),
        patch("searchat.config.PathResolver.get_shared_search_dir", return_value=temp_search_dir),
        patch.object(UnifiedIndexer, "_get_embedder", return_value=_fake_embedder()),
    ):
        result = run_rebuild_derived([])

    captured = capsys.readouterr()
    assert result == 0
    assert "Rebuild complete" in captured.out
    assert "Conversations processed:" in captured.out
    assert "Exchanges rebuilt:" in captured.out
    assert "Embeddings rebuilt:" in captured.out
    assert "Forced full rebuild:" in captured.out
    assert "Time:" in captured.out


def test_rebuild_derived_json_output(temp_search_dir: Path, capsys) -> None:
    from searchat.cli.rebuild_cmd import run_rebuild_derived

    _seed_two_conversations(temp_search_dir)
    config = Config.load()

    with (
        patch("searchat.config.Config.load", return_value=config),
        patch("searchat.config.PathResolver.get_shared_search_dir", return_value=temp_search_dir),
        patch.object(UnifiedIndexer, "_get_embedder", return_value=_fake_embedder()),
    ):
        result = run_rebuild_derived(["--json"])

    captured = capsys.readouterr()
    assert result == 0
    payload = json.loads(captured.out)

    assert set(payload.keys()) == {
        "conversations_processed",
        "exchanges_rebuilt",
        "embeddings_rebuilt",
        "rebuild_time_seconds",
        "forced",
    }
    assert payload["conversations_processed"] == 2
    assert payload["exchanges_rebuilt"] == 4
    assert payload["embeddings_rebuilt"] == 4
    assert payload["forced"] is False


def test_rebuild_derived_succeeds_on_empty_search_dir(temp_search_dir: Path, capsys) -> None:
    """No DB exists yet — must still succeed (explicit read_only=False creates it)."""
    from searchat.cli.rebuild_cmd import run_rebuild_derived

    assert not _db_path(temp_search_dir).exists()
    config = Config.load()

    with (
        patch("searchat.config.Config.load", return_value=config),
        patch("searchat.config.PathResolver.get_shared_search_dir", return_value=temp_search_dir),
        patch.object(UnifiedIndexer, "_get_embedder", return_value=_fake_embedder()),
    ):
        result = run_rebuild_derived(["--json"])

    captured = capsys.readouterr()
    assert result == 0
    payload = json.loads(captured.out)
    assert payload["conversations_processed"] == 0
    assert _db_path(temp_search_dir).exists()


def test_rebuild_derived_returns_one_and_prints_error_on_failure(
    temp_search_dir: Path, capsys
) -> None:
    from searchat.cli.rebuild_cmd import run_rebuild_derived

    config = Config.load()

    with (
        patch("searchat.config.Config.load", return_value=config),
        patch("searchat.config.PathResolver.get_shared_search_dir", return_value=temp_search_dir),
        patch.object(UnifiedIndexer, "rebuild_derived", side_effect=RuntimeError("boom")),
    ):
        result = run_rebuild_derived([])

    captured = capsys.readouterr()
    assert result == 1
    assert "Error: failed to rebuild derived data" in captured.err
    assert "boom" in captured.err


# ---------------------------------------------------------------------------
# reingest-sources: guard stays intact through the new CLI surface
# ---------------------------------------------------------------------------

def test_reingest_sources_guard_blocks_without_force(temp_search_dir: Path, capsys) -> None:
    """Existing-index guard fires for real — no source scan ever starts."""
    from searchat.cli.rebuild_cmd import run_reingest_sources

    indices_dir = temp_search_dir / "data" / "indices"
    indices_dir.mkdir(parents=True, exist_ok=True)
    (indices_dir / "embeddings.faiss").write_bytes(b"FAISSSTUB")

    config = Config.load()

    with (
        patch("searchat.config.Config.load", return_value=config),
        patch("searchat.config.PathResolver.get_shared_search_dir", return_value=temp_search_dir),
    ):
        result = run_reingest_sources([])

    captured = capsys.readouterr()
    assert result == 1
    assert "Existing index detected" in captured.err


def test_reingest_sources_force_success(temp_search_dir: Path, capsys) -> None:
    from searchat.cli.rebuild_cmd import run_reingest_sources

    indices_dir = temp_search_dir / "data" / "indices"
    indices_dir.mkdir(parents=True, exist_ok=True)
    (indices_dir / "embeddings.faiss").write_bytes(b"FAISSSTUB")

    config = Config.load()
    fake_stats = IndexStats(
        total_conversations=3,
        total_messages=10,
        index_time_seconds=1.5,
        parquet_size_mb=0.0,
        faiss_size_mb=0.0,
    )
    fake_indexer = MagicMock()
    fake_indexer.index_all.return_value = fake_stats

    with (
        patch("searchat.config.Config.load", return_value=config),
        patch("searchat.config.PathResolver.get_shared_search_dir", return_value=temp_search_dir),
        patch("searchat.core.indexer.ConversationIndexer", return_value=fake_indexer),
    ):
        result = run_reingest_sources(["--force"])

    captured = capsys.readouterr()
    assert result == 0
    assert "Reingest complete." in captured.out
    assert "3" in captured.out
    assert "10" in captured.out
    fake_indexer.index_all.assert_called_once_with(force=True)


def test_reingest_sources_never_bypasses_guard_without_explicit_force(
    temp_search_dir: Path, capsys
) -> None:
    """CLI must pass through args.force as-is — never silently force=True."""
    from searchat.cli.rebuild_cmd import run_reingest_sources

    config = Config.load()
    fake_indexer = MagicMock()
    fake_indexer.index_all.side_effect = RuntimeError(
        "Existing index detected. Full rebuild will REPLACE all indexed data."
    )

    with (
        patch("searchat.config.Config.load", return_value=config),
        patch("searchat.config.PathResolver.get_shared_search_dir", return_value=temp_search_dir),
        patch("searchat.core.indexer.ConversationIndexer", return_value=fake_indexer),
    ):
        result = run_reingest_sources([])

    captured = capsys.readouterr()
    assert result == 1
    assert "Existing index detected" in captured.err
    fake_indexer.index_all.assert_called_once_with(force=False)
