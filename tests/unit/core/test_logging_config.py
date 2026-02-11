"""Tests for searchat.core.logging_config."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from unittest.mock import patch

from searchat.core.logging_config import LogConfig, setup_logging, get_logger


class TestLogConfig:
    """Tests for LogConfig defaults."""

    def test_defaults(self):
        cfg = LogConfig()
        assert cfg.level == "INFO"
        assert cfg.file_enabled is True
        assert cfg.file_backup_count == 5
        assert cfg.use_rich_console is True


class TestSetupLogging:
    """Tests for setup_logging."""

    def _cleanup_root(self):
        root = logging.getLogger()
        for handler in root.handlers[:]:
            handler.close()
        root.handlers.clear()
        root.setLevel(logging.WARNING)

    def test_file_handler_created(self, tmp_path):
        log_file = tmp_path / "test.log"
        cfg = LogConfig(
            level="DEBUG",
            file_enabled=True,
            file_path=str(log_file),
            use_rich_console=False,
        )
        try:
            setup_logging(cfg)
            root = logging.getLogger()
            handler_types = [type(h) for h in root.handlers]
            assert RotatingFileHandler in handler_types
            assert root.level == logging.DEBUG
        finally:
            self._cleanup_root()

    def test_file_handler_disabled(self):
        cfg = LogConfig(
            file_enabled=False,
            use_rich_console=False,
        )
        try:
            setup_logging(cfg)
            root = logging.getLogger()
            for h in root.handlers:
                assert not isinstance(h, RotatingFileHandler)
        finally:
            self._cleanup_root()

    def test_rich_console_handler(self):
        cfg = LogConfig(
            file_enabled=False,
            use_rich_console=True,
        )
        try:
            setup_logging(cfg)
            root = logging.getLogger()
            assert len(root.handlers) == 1
        finally:
            self._cleanup_root()

    def test_rich_import_fallback(self):
        cfg = LogConfig(
            file_enabled=False,
            use_rich_console=True,
        )
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "rich.logging":
                raise ImportError("no rich")
            return real_import(name, *args, **kwargs)

        try:
            with patch("builtins.__import__", side_effect=mock_import):
                setup_logging(cfg)
            root = logging.getLogger()
            assert len(root.handlers) == 1
            assert isinstance(root.handlers[0], logging.StreamHandler)
        finally:
            self._cleanup_root()

    def test_plain_console_handler(self):
        cfg = LogConfig(
            file_enabled=False,
            use_rich_console=False,
        )
        try:
            setup_logging(cfg)
            root = logging.getLogger()
            assert len(root.handlers) == 1
            assert isinstance(root.handlers[0], logging.StreamHandler)
        finally:
            self._cleanup_root()

    def test_clears_existing_handlers(self):
        root = logging.getLogger()
        root.addHandler(logging.StreamHandler())
        initial_count = len(root.handlers)
        assert initial_count >= 1

        cfg = LogConfig(file_enabled=False, use_rich_console=False)
        try:
            setup_logging(cfg)
            assert len(root.handlers) == 1
        finally:
            self._cleanup_root()


class TestGetLogger:
    """Tests for get_logger."""

    def test_returns_logger(self):
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.module"
