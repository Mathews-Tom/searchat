"""Unit tests for `searchat-setup-index` (searchat.cli.setup_index).

Covers the DuckDB-native indexer selection introduced when this script was
migrated off the deprecated Parquet+FAISS ConversationIndexer (see the
"clean-install-dependency-audit" fix): the default (safe) path must go
through UnifiedIndexer without requiring the deprecated legacy engine, while
an explicit full rebuild over *existing* data must still route through the
guarded legacy ConversationIndexer engine used by `reingest-sources`.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from searchat.config import Config, PathResolver
from searchat.core.unified_indexer import UnifiedIndexer


def _write_jsonl(path: Path, lines: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")


def _fake_embedder() -> MagicMock:
    """Deterministic stand-in for SentenceTransformer — avoids loading a real model."""
    embedder = MagicMock()
    embedder.encode.side_effect = lambda batch, **kwargs: np.zeros(
        (len(batch), 384), dtype=np.float32
    )
    return embedder


@pytest.fixture
def only_claude_connector(tmp_path, monkeypatch):
    """Restrict connector discovery to a single, controlled Claude directory."""
    claude_dir = tmp_path / ".claude" / "projects"
    monkeypatch.setattr(PathResolver, "resolve_claude_dirs", lambda config=None: [claude_dir])
    monkeypatch.setattr(PathResolver, "resolve_vibe_dirs", lambda: [])
    monkeypatch.setattr(PathResolver, "resolve_opencode_dirs", lambda config=None: [])
    monkeypatch.setattr(PathResolver, "resolve_codex_dirs", lambda config=None: [])
    monkeypatch.setattr(PathResolver, "resolve_gemini_dirs", lambda config=None: [])
    monkeypatch.setattr(PathResolver, "resolve_continue_dirs", lambda config=None: [])
    monkeypatch.setattr(PathResolver, "resolve_cursor_dirs", lambda config=None: [])
    monkeypatch.setattr(PathResolver, "resolve_aider_dirs", lambda config=None: [])
    monkeypatch.setattr(PathResolver, "resolve_omp_dirs", lambda config=None: [])
    return claude_dir


def _seed_one_conversation(claude_dir: Path) -> Path:
    conv_path = claude_dir / "project-one" / "conv1.jsonl"
    _write_jsonl(
        conv_path,
        [
            {"type": "user", "message": {"content": "How do I reverse a list?"}, "timestamp": "2026-01-01T10:00:00"},
            {"type": "assistant", "message": {"content": "Use slicing: lst[::-1]"}, "timestamp": "2026-01-01T10:00:30"},
        ],
    )
    return conv_path


def test_fresh_install_uses_unified_indexer_not_legacy(
    temp_search_dir: Path, only_claude_connector: Path, capsys
) -> None:
    """No existing index: the default path must build via UnifiedIndexer.

    Never touches ConversationIndexer (which requires the palace/legacy
    extras) — reproduces the fix for searchat-setup-index crashing with
    `ModuleNotFoundError: No module named 'faiss'` on a clean install.
    """
    from searchat.cli.setup_index import main as setup_main

    _seed_one_conversation(only_claude_connector)
    config = Config.load()

    with (
        patch("searchat.config.Config.load", return_value=config),
        patch("searchat.config.PathResolver.get_shared_search_dir", return_value=temp_search_dir),
        patch("searchat.cli.setup_index.setup_logging"),
        patch.object(UnifiedIndexer, "_get_embedder", return_value=_fake_embedder()),
        patch("searchat.core.indexer.ConversationIndexer") as legacy_cls,
    ):
        setup_main(argv=[])

    legacy_cls.assert_not_called()

    captured = capsys.readouterr()
    assert "Index Build Complete" in captured.out
    assert "New conversations indexed: 1" in captured.out

    db_path = config.storage.resolve_duckdb_path(temp_search_dir)
    assert db_path.exists()


def test_second_run_is_append_only_and_finds_nothing_new(
    temp_search_dir: Path, only_claude_connector: Path, capsys
) -> None:
    """Running again with no new files reports up-to-date without reindexing."""
    from searchat.cli.setup_index import main as setup_main

    _seed_one_conversation(only_claude_connector)
    config = Config.load()

    with (
        patch("searchat.config.Config.load", return_value=config),
        patch("searchat.config.PathResolver.get_shared_search_dir", return_value=temp_search_dir),
        patch("searchat.cli.setup_index.setup_logging"),
        patch.object(UnifiedIndexer, "_get_embedder", return_value=_fake_embedder()),
    ):
        setup_main(argv=[])
        capsys.readouterr()  # discard first-run output

        setup_main(argv=[])

    captured = capsys.readouterr()
    assert "No new conversations to index" in captured.out
    assert "Index Build Complete" not in captured.out
    assert "Index Update Complete" not in captured.out


def test_force_with_existing_index_routes_to_legacy_engine(
    temp_search_dir: Path, only_claude_connector: Path
) -> None:
    """--force over an *existing* index must still use the guarded legacy
    ConversationIndexer (same engine as `reingest-sources`), never silently
    downgraded to the safe UnifiedIndexer path."""
    from searchat.cli.setup_index import main as setup_main
    from searchat.models import IndexStats

    _seed_one_conversation(only_claude_connector)
    config = Config.load()

    fake_stats = IndexStats(
        total_conversations=1,
        total_messages=2,
        index_time_seconds=0.01,
        parquet_size_mb=0.0,
        faiss_size_mb=0.0,
    )
    fake_legacy_indexer = MagicMock()
    fake_legacy_indexer.index_all.return_value = fake_stats

    with (
        patch("searchat.config.Config.load", return_value=config),
        patch("searchat.config.PathResolver.get_shared_search_dir", return_value=temp_search_dir),
        patch("searchat.cli.setup_index.setup_logging"),
        patch.object(UnifiedIndexer, "_get_embedder", return_value=_fake_embedder()),
    ):
        # First run creates the DuckDB store so has_index is True next time.
        setup_main(argv=[])

        with patch(
            "searchat.core.indexer.ConversationIndexer", return_value=fake_legacy_indexer
        ) as legacy_cls:
            setup_main(argv=["--force"])

    legacy_cls.assert_called_once()
    fake_legacy_indexer.index_all.assert_called_once()
    assert fake_legacy_indexer.index_all.call_args.kwargs["force"] is True
