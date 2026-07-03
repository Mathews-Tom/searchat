"""Read-only disk accounting for registered connectors and Searchat's own footprint.

M6 -- Disk manager dashboard. Aggregates per-connector on-disk usage (a
`du`-equivalent walk of each connector's watch directories) plus the
indexed-vs-unindexed delta sourced from `source_file_state`, and Searchat's
own `~/.searchat` subdirectory footprint (index, backups, models, expertise,
and any other subdirectory found).

Every function in this module only reads the filesystem and the DuckDB
store opened read-only -- there is no mutation code path here, matching the
"report first" ordering from the enhancement catalog (M7 cruft advisor and
M11 dedup detection build on this module but stay report-only too).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from searchat.config import Config


@dataclass(frozen=True)
class _DirectoryUsage:
    """`du`-equivalent size/count for one directory tree, walked recursively."""

    total_size_bytes: int
    file_count: int


def _walk_directory(path: Path) -> _DirectoryUsage:
    """Recursively sum file sizes and counts under `path`, `du`-style.

    Symlinks are not followed (matches `du`'s default POSIX behavior) and
    unreadable entries are skipped rather than raised, so one permission
    error or a file removed mid-walk never fails the whole report.
    """
    if not path.exists():
        return _DirectoryUsage(total_size_bytes=0, file_count=0)
    total_size = 0
    file_count = 0
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            entries = list(current.iterdir())
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.is_symlink():
                    continue
                if entry.is_dir():
                    stack.append(entry)
                    continue
                size = entry.stat().st_size
            except OSError:
                continue
            total_size += size
            file_count += 1
    return _DirectoryUsage(total_size_bytes=total_size, file_count=file_count)


def _connector_watch_dirs(connector: Any, config: Config) -> list[Path]:
    """Per-connector watch directories, deduplicated.

    Mirrors `registry.discover_watch_dirs`'s per-connector resolution (a
    `watch_dirs(config)` method when the connector defines one, else the
    deduplicated parent directories of `discover_files(config)`) but keeps
    the result scoped to one connector instead of flattening across all of
    them, which per-agent accounting requires.
    """
    watch_dirs_fn = getattr(connector, "watch_dirs", None)
    if callable(watch_dirs_fn):
        try:
            return [d for d in watch_dirs_fn(config) if d.exists()]
        except Exception:
            return []
    try:
        files = connector.discover_files(config)
    except Exception:
        return []
    seen: set[str] = set()
    dirs: list[Path] = []
    for file_path in files:
        parent = file_path.parent
        key = str(parent.resolve()) if parent.exists() else str(parent)
        if key in seen:
            continue
        seen.add(key)
        dirs.append(parent)
    return dirs


@dataclass(frozen=True)
class AgentDiskUsage:
    """Read-only disk-usage summary for one registered connector."""

    connector: str
    watch_dirs: tuple[str, ...]
    total_size_bytes: int
    total_file_count: int
    conversation_file_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "connector": self.connector,
            "watch_dirs": list(self.watch_dirs),
            "total_size_bytes": self.total_size_bytes,
            "total_file_count": self.total_file_count,
            "conversation_file_count": self.conversation_file_count,
        }


def compute_agent_disk_usage(connector: Any, config: Config) -> AgentDiskUsage:
    """Build the size/count summary for one connector.

    `total_size_bytes`/`total_file_count` walk every file under the
    connector's watch directories (the `du`-equivalent figure the M6
    acceptance criterion is measured against), independent of whether a
    given file is a conversation the connector recognizes.
    `conversation_file_count` is scoped to `discover_files` results only --
    non-conversation files in the same directory (harness state, caches)
    are counted toward the size total but not toward this count.
    """
    watch_dirs = _connector_watch_dirs(connector, config)
    total_size = 0
    total_count = 0
    for watch_dir in watch_dirs:
        usage = _walk_directory(watch_dir)
        total_size += usage.total_size_bytes
        total_count += usage.file_count

    try:
        conversation_files = connector.discover_files(config)
    except Exception:
        conversation_files = []

    return AgentDiskUsage(
        connector=connector.name,
        watch_dirs=tuple(str(d) for d in watch_dirs),
        total_size_bytes=total_size,
        total_file_count=total_count,
        conversation_file_count=len(conversation_files),
    )
