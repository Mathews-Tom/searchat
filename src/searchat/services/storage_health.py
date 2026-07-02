"""Storage inspection and safe metadata normalization helpers."""

from __future__ import annotations
import json
import re
from dataclasses import dataclass
from pathlib import Path

import duckdb

from searchat.services.backup import BackupManager
from searchat.services.storage_contracts import (
    BACKUP_MANIFEST_FILE,
    BACKUP_METADATA_FILE,
    BackupManifest,
    StorageCompatibilityError,
    index_metadata_path,
)
from searchat.services.storage_migrations import (
    migrate_backup_manifest,
    migrate_backup_metadata,
    migrate_index_metadata_root,
)


@dataclass(frozen=True)
class DatasetIndexTarget:
    scope: str
    dataset_root: Path
    metadata_path: Path
    label: str


@dataclass(frozen=True)
class StorageIssue:
    severity: str
    scope: str
    path: Path
    message: str
    repairable: bool = False


@dataclass(frozen=True)
class StorageHealthReport:
    search_dir: Path
    issues: list[StorageIssue]
    repairs_applied: int = 0

    @property
    def is_healthy(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    @property
    def repairable_issues(self) -> list[StorageIssue]:
        return [issue for issue in self.issues if issue.repairable]


def _iter_index_targets(search_dir: Path) -> list[DatasetIndexTarget]:
    targets = [
        DatasetIndexTarget(
            scope="index_metadata",
            dataset_root=search_dir,
            metadata_path=index_metadata_path(search_dir),
            label="live dataset",
        )
    ]

    backups_dir = search_dir / "backups"
    if not backups_dir.exists():
        return targets

    for backup_dir in sorted(path for path in backups_dir.iterdir() if path.is_dir()):
        manifest_path = backup_dir / BACKUP_MANIFEST_FILE
        if manifest_path.exists():
            try:
                manifest = BackupManifest.from_dict(json.loads(manifest_path.read_text(encoding="utf-8")))
            except StorageCompatibilityError:
                continue
            if manifest.backup_mode != "full" or manifest.encrypted:
                continue
        metadata_path = index_metadata_path(backup_dir)
        if metadata_path.exists():
            targets.append(
                DatasetIndexTarget(
                    scope="backup_index_metadata",
                    dataset_root=backup_dir,
                    metadata_path=metadata_path,
                    label=f"backup dataset '{backup_dir.name}'",
                )
            )

    return targets


def _inspect_index_target(
    target: DatasetIndexTarget,
    *,
    embedding_model: str | None,
) -> StorageIssue | None:
    if not target.metadata_path.exists():
        return None
    try:
        plan = migrate_index_metadata_root(
            target.dataset_root,
            embedding_model=embedding_model,
            apply=False,
        )
        plan.migrated.validate_compatible(embedding_model=embedding_model)
        if plan.has_changes:
            return StorageIssue(
                severity="warning",
                scope=target.scope,
                path=target.metadata_path,
                message=(
                    f"{target.label.capitalize()} index metadata can be migrated by normalizing fields: "
                    + ", ".join(plan.changed_fields)
                ),
                repairable=True,
            )
    except (FileNotFoundError, StorageCompatibilityError) as exc:
        return StorageIssue(
            severity="error",
            scope=target.scope,
            path=target.metadata_path,
            message=str(exc),
        )
    return None


def inspect_storage_health(
    search_dir: Path,
    *,
    embedding_model: str | None = None,
) -> StorageHealthReport:
    issues: list[StorageIssue] = []
    backup_manager = BackupManager(search_dir)
    for target in _iter_index_targets(search_dir):
        issue = _inspect_index_target(target, embedding_model=embedding_model)
        if issue is not None:
            issues.append(issue)

    backups_dir = search_dir / "backups"
    if backups_dir.exists():
        for backup_dir in sorted(path for path in backups_dir.iterdir() if path.is_dir()):
            metadata_path = backup_dir / BACKUP_METADATA_FILE
            if metadata_path.exists():
                try:
                    plan = migrate_backup_metadata(backup_dir, apply=False)
                    if plan.has_changes:
                        issues.append(
                            StorageIssue(
                                severity="warning",
                                scope="backup_metadata",
                                path=metadata_path,
                                message=(
                                    "Backup metadata can be normalized to the current contract version: "
                                    + ", ".join(plan.changed_fields)
                                ),
                                repairable=True,
                            )
                        )
                except StorageCompatibilityError as exc:
                    issues.append(
                        StorageIssue(
                            severity="error",
                            scope="backup_metadata",
                            path=metadata_path,
                            message=str(exc),
                        )
                    )
            manifest_path = backup_dir / BACKUP_MANIFEST_FILE
            manifest_valid = False
            if manifest_path.exists():
                try:
                    plan = migrate_backup_manifest(backup_dir, apply=False)
                    if plan.has_changes:
                        issues.append(
                            StorageIssue(
                                severity="warning",
                                scope="backup_manifest",
                                path=manifest_path,
                                message=(
                                    "Backup manifest can be normalized to the current contract version: "
                                    + ", ".join(plan.changed_fields)
                                ),
                                repairable=True,
                            )
                        )
                    manifest_valid = True
                except StorageCompatibilityError as exc:
                    issues.append(
                        StorageIssue(
                            severity="error",
                            scope="backup_manifest",
                            path=manifest_path,
                            message=str(exc),
                        )
                    )
            if manifest_valid:
                artifact = backup_manager.validate_backup_artifact(backup_dir.name, verify_hashes=False)
                if not artifact.get("valid"):
                    errors = [
                        str(error)
                        for error in artifact.get("errors", [])
                        if "manifest version mismatch" not in str(error)
                    ]
                    if errors:
                        issues.append(
                            StorageIssue(
                                severity="error",
                                scope="backup_chain",
                                path=backup_dir,
                                message=(
                                    f"Backup chain validation failed for '{backup_dir.name}': "
                                    + "; ".join(errors)
                                ),
                            )
                        )

    return StorageHealthReport(search_dir=search_dir, issues=issues)


def repair_storage_metadata(
    search_dir: Path,
    *,
    embedding_model: str | None = None,
) -> StorageHealthReport:
    repairs_applied = 0

    for target in _iter_index_targets(search_dir):
        try:
            plan = migrate_index_metadata_root(
                target.dataset_root,
                embedding_model=embedding_model,
                apply=True,
            )
            if plan.has_changes:
                repairs_applied += 1
        except (FileNotFoundError, StorageCompatibilityError):
            pass

    backups_dir = search_dir / "backups"
    if backups_dir.exists():
        for backup_dir in sorted(path for path in backups_dir.iterdir() if path.is_dir()):
            metadata_path = backup_dir / BACKUP_METADATA_FILE
            if metadata_path.exists():
                try:
                    plan = migrate_backup_metadata(backup_dir, apply=True)
                    if plan.has_changes:
                        repairs_applied += 1
                except StorageCompatibilityError:
                    pass
            manifest_path = backup_dir / BACKUP_MANIFEST_FILE
            if manifest_path.exists():
                try:
                    plan = migrate_backup_manifest(backup_dir, apply=True)
                    if plan.has_changes:
                        repairs_applied += 1
                except StorageCompatibilityError:
                    pass

    refreshed = inspect_storage_health(search_dir, embedding_model=embedding_model)
    return StorageHealthReport(
        search_dir=search_dir,
        issues=refreshed.issues,
        repairs_applied=repairs_applied,
    )


# ---------------------------------------------------------------------------
# Storage doctor diagnostics: live-data size estimation (searchat doctor)
# ---------------------------------------------------------------------------

_DUCKDB_SIZE_UNITS = {
    "bytes": 1,
    "kib": 1024,
    "mib": 1024**2,
    "gib": 1024**3,
    "tib": 1024**4,
    "pib": 1024**5,
}


def _parse_duckdb_size(text: str) -> int:
    """Parse a DuckDB-formatted size string (e.g. '1.4 GiB', '0 bytes') to bytes."""
    match = re.match(r"^\s*([\d.]+)\s*([A-Za-z]+)\s*$", text)
    if not match:
        return 0
    multiplier = _DUCKDB_SIZE_UNITS.get(match.group(2).lower())
    if multiplier is None:
        return 0
    return int(float(match.group(1)) * multiplier)


@dataclass(frozen=True)
class DatabaseSizeInfo:
    """Raw PRAGMA database_size fields for a DuckDB file, read-only."""

    total_bytes: int
    block_size: int
    total_blocks: int
    used_blocks: int
    free_blocks: int
    wal_bytes: int


_EMPTY_DATABASE_SIZE_INFO = DatabaseSizeInfo(
    total_bytes=0, block_size=0, total_blocks=0, used_blocks=0, free_blocks=0, wal_bytes=0
)


def inspect_database_size(db_path: Path) -> DatabaseSizeInfo:
    """Read PRAGMA database_size for `db_path` without mutating it.

    Returns an all-zero report when `db_path` does not exist yet (fresh install).
    """
    if not db_path.exists():
        return _EMPTY_DATABASE_SIZE_INFO
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        cursor = con.execute("PRAGMA database_size")
        row = cursor.fetchone()
        if row is None:
            return _EMPTY_DATABASE_SIZE_INFO
        columns = {desc[0]: value for desc, value in zip(cursor.description, row)}
        block_size = int(columns.get("block_size", 0) or 0)
        total_blocks = int(columns.get("total_blocks", 0) or 0)
        used_blocks = int(columns.get("used_blocks", 0) or 0)
        free_blocks = int(columns.get("free_blocks", 0) or 0)
        wal_bytes = _parse_duckdb_size(str(columns.get("wal_size", "0 bytes")))
        return DatabaseSizeInfo(
            total_bytes=block_size * total_blocks,
            block_size=block_size,
            total_blocks=total_blocks,
            used_blocks=used_blocks,
            free_blocks=free_blocks,
            wal_bytes=wal_bytes,
        )
    finally:
        con.close()


def estimate_live_data_size(db_path: Path) -> int:
    """Estimate the bytes actually occupied by live tables in `db_path`.

    Sums the distinct storage blocks referenced by `pragma_storage_info` across
    the `main` schema and every `fts_main_*` schema, deduplicated so segments
    packed into the same block are not double-counted. This is the "live"
    footprint that `compute_bloat_ratio` compares against the on-disk file
    size — blocks that no longer belong to any current table (freed by
    deletes/updates/rebuilds but not reclaimed by DuckDB's allocator) are
    invisible to `pragma_storage_info` and therefore excluded here, which is
    exactly the bloat `searchat compact` (M3) reclaims.

    Returns 0 when `db_path` does not exist yet.
    """
    if not db_path.exists():
        return 0
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        size_row = con.execute("PRAGMA database_size").fetchone()
        if size_row is None:
            return 0
        columns = {desc[0]: value for desc, value in zip(con.description, size_row)}
        block_size = int(columns.get("block_size", 0) or 0)
        if block_size <= 0:
            return 0

        schemas = [
            row[0]
            for row in con.execute(
                "SELECT DISTINCT table_schema FROM information_schema.tables "
                "WHERE table_schema = 'main' OR table_schema LIKE 'fts_main_%'"
            ).fetchall()
        ]

        live_blocks: set[int] = set()
        for schema in schemas:
            tables = [
                row[0]
                for row in con.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = ?",
                    [schema],
                ).fetchall()
            ]
            for table in tables:
                qualified = f'"{schema}"."{table}"'
                try:
                    block_rows = con.execute(
                        "SELECT DISTINCT block_id FROM pragma_storage_info(?) "
                        "WHERE block_id IS NOT NULL AND block_id >= 0",
                        [qualified],
                    ).fetchall()
                except duckdb.Error:
                    continue
                live_blocks.update(int(row[0]) for row in block_rows)

        return len(live_blocks) * block_size
    finally:
        con.close()
