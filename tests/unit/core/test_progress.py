"""Tests for searchat.core.progress."""
from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from searchat.core.progress import (
    NullProgressAdapter,
    LoggingProgressAdapter,
    RichProgressAdapter,
    create_progress,
)



class TestNullProgressAdapter:
    """Verify NullProgressAdapter is a no-op."""

    def test_all_methods_callable(self):
        adapter = NullProgressAdapter()
        adapter.update_phase("test")
        adapter.update_file_progress(1, 10, "file.py")
        adapter.update_embedding_progress(5, 50)
        adapter.update_stats(10, 100, 50)
        adapter.finish()


class TestLoggingProgressAdapter:
    """Tests for LoggingProgressAdapter."""

    def test_update_phase_logs(self, caplog):
        adapter = LoggingProgressAdapter()
        with caplog.at_level(logging.INFO):
            adapter.update_phase("Scanning files")
        assert "Phase: Scanning files" in caplog.text

    def test_file_progress_logs_at_intervals(self, caplog):
        adapter = LoggingProgressAdapter()
        with caplog.at_level(logging.INFO):
            # 0% (initial) → should log
            adapter.update_file_progress(0, 100, "a.py")
            # 5% → same bucket as 0%, skip
            adapter.update_file_progress(5, 100, "b.py")
            # 10% → new bucket → log
            adapter.update_file_progress(10, 100, "c.py")

        # Should have exactly 2 log entries (0% and 10%)
        file_lines = [r for r in caplog.records if "Processing files" in r.message]
        assert len(file_lines) == 2

    def test_file_progress_zero_total(self, caplog):
        adapter = LoggingProgressAdapter()
        with caplog.at_level(logging.INFO):
            adapter.update_file_progress(0, 0, "a.py")
        file_lines = [r for r in caplog.records if "Processing files" in r.message]
        assert len(file_lines) == 0

    def test_embedding_progress_logs_at_intervals(self, caplog):
        adapter = LoggingProgressAdapter()
        with caplog.at_level(logging.INFO):
            adapter.update_embedding_progress(0, 100)
            adapter.update_embedding_progress(5, 100)
            adapter.update_embedding_progress(20, 100)

        embed_lines = [r for r in caplog.records if "Generating embeddings" in r.message]
        assert len(embed_lines) == 2

    def test_embedding_progress_zero_total(self, caplog):
        adapter = LoggingProgressAdapter()
        with caplog.at_level(logging.INFO):
            adapter.update_embedding_progress(0, 0)
        embed_lines = [r for r in caplog.records if "Generating embeddings" in r.message]
        assert len(embed_lines) == 0

    def test_update_stats(self, caplog):
        adapter = LoggingProgressAdapter()
        with caplog.at_level(logging.INFO):
            adapter.update_stats(10, 200, 150)
        assert "10 conversations" in caplog.text
        assert "200 chunks" in caplog.text

    def test_finish(self, caplog):
        adapter = LoggingProgressAdapter()
        with caplog.at_level(logging.INFO):
            adapter.finish()
        assert "Progress complete" in caplog.text


class TestCreateProgress:
    """Tests for create_progress factory."""

    def test_force_logging(self):
        adapter = create_progress(use_rich=False)
        assert isinstance(adapter, LoggingProgressAdapter)

    def test_force_rich(self):
        adapter = create_progress(use_rich=True)
        assert isinstance(adapter, RichProgressAdapter)

    def test_auto_detect_non_tty(self, monkeypatch):
        monkeypatch.setattr("sys.stdout.isatty", lambda: False)
        adapter = create_progress(use_rich=None)
        assert isinstance(adapter, LoggingProgressAdapter)

    def test_auto_detect_tty(self, monkeypatch):
        monkeypatch.setattr("sys.stdout.isatty", lambda: True)
        adapter = create_progress(use_rich=None)
        assert isinstance(adapter, RichProgressAdapter)

    def test_rich_import_error_fallback(self, monkeypatch):
        """When Rich is unavailable, fall back to logging adapter."""
        def raise_import_error():
            raise ImportError("No rich")

        monkeypatch.setattr(
            "searchat.core.progress.RichProgressAdapter.__init__",
            lambda self: raise_import_error(),
        )
        adapter = create_progress(use_rich=True)
        assert isinstance(adapter, LoggingProgressAdapter)


class TestRichProgressAdapter:
    """Tests for RichProgressAdapter exercising all methods."""

    def test_init_creates_progress_and_console(self):
        adapter = RichProgressAdapter()
        assert adapter.console is not None
        assert adapter.progress is not None
        assert adapter.file_task is None
        assert adapter.embed_task is None
        assert adapter.phase_text == "Initializing..."

    def test_update_phase(self):
        adapter = RichProgressAdapter()
        adapter.update_phase("Scanning")
        assert adapter.phase_text == "Scanning"
        # live should have been started
        assert adapter.live is not None

    def test_update_file_progress(self):
        adapter = RichProgressAdapter()
        adapter.update_file_progress(1, 10, "a.py")
        assert adapter.file_task is not None
        # Second call reuses task
        adapter.update_file_progress(2, 10, "b.py")

    def test_update_embedding_progress(self):
        adapter = RichProgressAdapter()
        adapter.update_embedding_progress(1, 20)
        assert adapter.embed_task is not None
        adapter.update_embedding_progress(5, 20)

    def test_update_stats(self):
        adapter = RichProgressAdapter()
        adapter.update_stats(5, 100, 50)
        assert adapter.stats["conversations"] == 5
        assert adapter.stats["chunks"] == 100
        assert adapter.stats["embeddings"] == 50

    def test_update_stats_with_live(self):
        adapter = RichProgressAdapter()
        adapter.update_phase("test")  # starts live
        adapter.update_stats(1, 2, 3)
        assert adapter.stats["conversations"] == 1

    def test_finish_stops_live(self):
        adapter = RichProgressAdapter()
        adapter.update_phase("test")  # starts live
        assert adapter.live is not None
        adapter.finish()

    def test_finish_without_live(self):
        adapter = RichProgressAdapter()
        adapter.finish()  # no-op when live is None

    def test_make_layout_returns_group(self):
        adapter = RichProgressAdapter()
        layout = adapter._make_layout()
        assert layout is not None

    def test_start_live_idempotent(self):
        adapter = RichProgressAdapter()
        adapter._start_live()
        live1 = adapter.live
        adapter._start_live()
        assert adapter.live is live1
