"""Centralized logging configuration for searchat."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from logging.handlers import RotatingFileHandler


# Third-party loggers that are excessively noisy at INFO level.
# Raised to WARNING so their debug/info chatter (HTTP round-trips,
# model weight loads, etc.) stays out of the console.
_NOISY_LOGGERS: tuple[str, ...] = (
    "httpx",
    "httpcore",
    "huggingface_hub",
    "sentence_transformers",
)

# Loggers whose WARNING-level output is still noise (e.g. the
# BertModel LOAD REPORT for benign UNEXPECTED keys like position_ids).
# Raised to ERROR so only genuine failures surface.
_NOISY_WARN_LOGGERS: tuple[str, ...] = (
    "transformers.utils.loading_report",
)


@dataclass
class LogConfig:
    """Logging configuration."""

    level: str = "INFO"
    file_enabled: bool = True
    file_path: str = "~/.searchat/logs/searchat.log"
    file_max_bytes: int = 10485760  # 10MB
    file_backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    use_rich_console: bool = True
    quiet_third_party: bool = True
    access_log_ignore: list[str] = field(
        default_factory=lambda: ["/api/status"],
    )


class _AccessLogFilter(logging.Filter):
    """Drop uvicorn access-log records for specific path prefixes."""

    def __init__(self, ignored_paths: list[str]) -> None:
        super().__init__()
        self._ignored = tuple(ignored_paths)

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for path in self._ignored:
            if f" {path} " in msg or f'"{path} ' in msg or f" {path}?" in msg:
                return False
        return True


def _install_access_log_filter(ignored_paths: list[str]) -> None:
    """Attach *_AccessLogFilter* to the ``uvicorn.access`` logger."""
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.addFilter(_AccessLogFilter(ignored_paths))


def setup_logging(config: LogConfig) -> None:
    """
    Configure logging with file rotation and optional Rich console output.

    Args:
        config: Logging configuration
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(config.format)

    # Add file handler if enabled
    if config.file_enabled:
        # Expand user path
        log_path = Path(config.file_path).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Create rotating file handler
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=config.file_max_bytes,
            backupCount=config.file_backup_count,
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Add console handler
    if config.use_rich_console:
        try:
            from rich.logging import RichHandler

            console_handler = RichHandler(rich_tracebacks=True)
            console_handler.setFormatter(logging.Formatter("%(message)s"))
        except ImportError:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
    else:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)

    # Suppress noisy third-party loggers (httpx, huggingface_hub, etc.)
    if config.quiet_third_party:
        for name in _NOISY_LOGGERS:
            logging.getLogger(name).setLevel(logging.WARNING)
        for name in _NOISY_WARN_LOGGERS:
            logging.getLogger(name).setLevel(logging.ERROR)

    # Install access-log filter on uvicorn.access to drop high-frequency
    # polling endpoints (e.g. /api/status) that flood the console.
    if config.access_log_ignore:
        _install_access_log_filter(config.access_log_ignore)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
