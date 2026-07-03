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
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb

from searchat.config import Config
from searchat.core.connectors.registry import detect_connector, get_connectors

# Age histogram bucket boundaries, in days, applied to each connector's
# discovered conversation files (mtime-based). The final bucket is open-ended.
_AGE_BUCKET_DAYS: tuple[int, ...] = (7, 30, 90, 365)
_AGE_BUCKET_LABELS: tuple[str, ...] = ("0-7d", "7-30d", "30-90d", "90-365d", "365d+")

# Searchat's own `~/.searchat` subdirectories included in self-accounting,
# labeled per the M6 acceptance criterion ("index/backup/model/expertise
# subdirectories are included"). `index` maps to `data/`, which holds the
# DuckDB store (source-of-truth + derived tables) and its supporting Parquet
# exports -- the single largest contributor to Searchat's own footprint.
_SELF_ACCOUNTING_SUBDIRS: tuple[tuple[str, str], ...] = (
    ("index", "data"),
    ("backups", "backups"),
    ("models", "models"),
    ("expertise", "expertise"),
    ("knowledge_graph", "knowledge_graph"),
    ("analytics", "analytics"),
    ("config", "config"),
    ("logs", "logs"),
)


def _age_bucket(age_days: float) -> str:
    for boundary, label in zip(_AGE_BUCKET_DAYS, _AGE_BUCKET_LABELS):
        if age_days < boundary:
            return label
    return _AGE_BUCKET_LABELS[-1]


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


def _read_indexed_paths_by_connector(db_path: Path) -> dict[str, set[str]]:
    """Return `{connector_name: {file_path, ...}}` for `status = 'indexed'` rows.

    Rows written before `connector_name` was threaded through (or by legacy
    code paths) have a null/empty `connector_name`; those are routed to the
    correct connector by re-running `detect_connector` on the stored path
    rather than being fanned out into every connector's set.
    """
    if not db_path.exists():
        return {}
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = con.execute(
            "SELECT connector_name, file_path FROM source_file_state WHERE status = 'indexed'"
        ).fetchall()
    except duckdb.Error:
        return {}
    finally:
        con.close()

    by_connector: dict[str, set[str]] = {}
    for connector_name, file_path in rows:
        name = connector_name
        if not name:
            try:
                name = detect_connector(Path(file_path)).name
            except ValueError:
                name = "unknown"
        by_connector.setdefault(name, set()).add(file_path)
    return by_connector


@dataclass(frozen=True)
class AgentDiskUsage:
    """Read-only disk-usage summary for one registered connector."""

    connector: str
    watch_dirs: tuple[str, ...]
    total_size_bytes: int
    total_file_count: int
    conversation_file_count: int
    indexed_file_count: int
    indexed_size_bytes: int
    unindexed_file_count: int
    unindexed_size_bytes: int
    oldest_conversation_age_days: float | None
    newest_conversation_age_days: float | None
    age_histogram: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "connector": self.connector,
            "watch_dirs": list(self.watch_dirs),
            "total_size_bytes": self.total_size_bytes,
            "total_file_count": self.total_file_count,
            "conversation_file_count": self.conversation_file_count,
            "indexed_file_count": self.indexed_file_count,
            "indexed_size_bytes": self.indexed_size_bytes,
            "unindexed_file_count": self.unindexed_file_count,
            "unindexed_size_bytes": self.unindexed_size_bytes,
            "oldest_conversation_age_days": self.oldest_conversation_age_days,
            "newest_conversation_age_days": self.newest_conversation_age_days,
            "age_histogram": dict(self.age_histogram),
        }


def compute_agent_disk_usage(
    connector: Any,
    config: Config,
    indexed_paths: set[str],
    *,
    now: datetime | None = None,
) -> AgentDiskUsage:
    """Build the disk-usage summary for one connector.

    `total_size_bytes`/`total_file_count` walk every file under the
    connector's watch directories (the `du`-equivalent figure the M6
    acceptance criterion is measured against), independent of whether a
    given file is a conversation the connector recognizes. Indexed/unindexed
    and age are scoped to `discover_files` results only -- non-conversation
    files in the same directory (harness state, caches) are counted toward
    the size total but never toward conversation/indexed/unindexed counts.
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

    reference = now or datetime.now()
    indexed_count = 0
    indexed_size = 0
    unindexed_count = 0
    unindexed_size = 0
    ages_days: list[float] = []
    histogram = {label: 0 for label in _AGE_BUCKET_LABELS}

    for file_path in conversation_files:
        try:
            stat = file_path.stat()
        except OSError:
            continue
        size = stat.st_size
        mtime = datetime.fromtimestamp(stat.st_mtime)
        age_days = max((reference - mtime).total_seconds() / 86400.0, 0.0)
        ages_days.append(age_days)
        histogram[_age_bucket(age_days)] += 1
        if str(file_path) in indexed_paths:
            indexed_count += 1
            indexed_size += size
        else:
            unindexed_count += 1
            unindexed_size += size

    return AgentDiskUsage(
        connector=connector.name,
        watch_dirs=tuple(str(d) for d in watch_dirs),
        total_size_bytes=total_size,
        total_file_count=total_count,
        conversation_file_count=len(conversation_files),
        indexed_file_count=indexed_count,
        indexed_size_bytes=indexed_size,
        unindexed_file_count=unindexed_count,
        unindexed_size_bytes=unindexed_size,
        oldest_conversation_age_days=max(ages_days) if ages_days else None,
        newest_conversation_age_days=min(ages_days) if ages_days else None,
        age_histogram=histogram,
    )


@dataclass(frozen=True)
class SubdirectoryUsage:
    """Read-only disk-usage summary for one Searchat self-accounting subdirectory."""

    label: str
    path: str
    exists: bool
    total_size_bytes: int
    file_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "path": self.path,
            "exists": self.exists,
            "total_size_bytes": self.total_size_bytes,
            "file_count": self.file_count,
        }


@dataclass(frozen=True)
class SearchatSelfUsage:
    """Read-only disk-usage summary for Searchat's own `~/.searchat` footprint."""

    search_dir: str
    subdirectories: tuple[SubdirectoryUsage, ...]
    total_size_bytes: int
    total_file_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "search_dir": self.search_dir,
            "subdirectories": [sub.to_dict() for sub in self.subdirectories],
            "total_size_bytes": self.total_size_bytes,
            "total_file_count": self.total_file_count,
        }


def compute_searchat_self_usage(search_dir: Path) -> SearchatSelfUsage:
    """Sum Searchat's own footprint across its known subdirectories.

    Always reports the `index`/`backups`/`models`/`expertise` subdirectories
    by name (size 0 when absent, e.g. a fresh install with no models
    downloaded yet) plus every other known subdirectory, so Searchat's own
    storage is never the invisible entry the enhancement analysis called out.
    """
    subdirs: list[SubdirectoryUsage] = []
    total_size = 0
    total_count = 0
    for label, dirname in _SELF_ACCOUNTING_SUBDIRS:
        sub_path = search_dir / dirname
        usage = _walk_directory(sub_path)
        subdirs.append(
            SubdirectoryUsage(
                label=label,
                path=str(sub_path),
                exists=sub_path.exists(),
                total_size_bytes=usage.total_size_bytes,
                file_count=usage.file_count,
            )
        )
        total_size += usage.total_size_bytes
        total_count += usage.file_count
    return SearchatSelfUsage(
        search_dir=str(search_dir),
        subdirectories=tuple(subdirs),
        total_size_bytes=total_size,
        total_file_count=total_count,
    )


@dataclass(frozen=True)
class DiskAccountingReport:
    """Unified, read-only disk-accounting report consumed by `searchat disk`
    and the `/api/disk` endpoint."""

    agents: tuple[AgentDiskUsage, ...]
    searchat_self: SearchatSelfUsage
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "agents": [agent.to_dict() for agent in self.agents],
            "searchat_self": self.searchat_self.to_dict(),
            "generated_at": self.generated_at,
        }


def build_disk_accounting_report(search_dir: Path, config: Config) -> DiskAccountingReport:
    """Assemble the full read-only disk-accounting report for `search_dir`.

    A connector whose accounting raises is skipped so one bad harness never
    fails the whole report -- the same resilience contract `storage_health`
    already applies to `estimate_harness_source_sizes` (M1).
    """
    db_path = config.storage.resolve_duckdb_path(search_dir)
    indexed_by_connector = _read_indexed_paths_by_connector(db_path)

    agents: list[AgentDiskUsage] = []
    for connector in get_connectors():
        try:
            indexed_paths = indexed_by_connector.get(connector.name, set())
            agents.append(compute_agent_disk_usage(connector, config, indexed_paths))
        except Exception:
            continue

    return DiskAccountingReport(
        agents=tuple(agents),
        searchat_self=compute_searchat_self_usage(search_dir),
        generated_at=datetime.now().isoformat(),
    )
