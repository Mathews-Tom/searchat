"""
Backup and restore functionality for Searchat indices and data.

CRITICAL: The Parquet files contain irreplaceable conversation data.
This module provides safe backup/restore operations to protect that data.
"""
from __future__ import annotations

import shutil
import json
from pathlib import Path
from typing import Any, cast
from datetime import datetime
import logging
import hashlib
import tempfile

from searchat.services.backup_crypto import decrypt_file, encrypt_file, get_backup_key

logger = logging.getLogger(__name__)


BACKUP_MANIFEST_FILE = "backup_manifest.json"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class BackupManifest:
    """Manifest describing backup contents and ancestry.

    This is the source of truth for:
    - backup type (full vs incremental)
    - whether payload files are encrypted
    - file-level integrity metadata
    - chain resolution (parent pointers)
    """

    def __init__(
        self,
        *,
        manifest_version: int,
        backup_mode: str,
        encrypted: bool,
        created_at: str,
        parent_name: str | None,
        files: dict[str, dict[str, object]],
        deleted_files: list[str],
    ):
        self.manifest_version = manifest_version
        self.backup_mode = backup_mode
        self.encrypted = encrypted
        self.created_at = created_at
        self.parent_name = parent_name
        self.files = files
        self.deleted_files = deleted_files

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_version": self.manifest_version,
            "backup_mode": self.backup_mode,
            "encrypted": self.encrypted,
            "created_at": self.created_at,
            "parent_name": self.parent_name,
            "files": self.files,
            "deleted_files": self.deleted_files,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackupManifest":
        parent = data.get("parent_name")
        parent_name = None if parent is None else str(parent)
        return cls(
            manifest_version=int(data.get("manifest_version", 1)),
            backup_mode=str(data.get("backup_mode", "full")),
            encrypted=bool(data.get("encrypted", False)),
            created_at=str(data.get("created_at", "")),
            parent_name=parent_name,
            files=cast(dict[str, dict[str, object]], data.get("files", {})),
            deleted_files=list(data.get("deleted_files", [])),
        )


class BackupMetadata:
    """Metadata for a backup."""

    def __init__(
        self,
        timestamp: str,
        backup_path: Path,
        source_path: Path,
        file_count: int,
        total_size_bytes: int,
        backup_type: str = "manual"
    ):
        self.timestamp = timestamp
        self.backup_path = backup_path
        self.source_path = source_path
        self.file_count = file_count
        self.total_size_bytes = total_size_bytes
        self.backup_type = backup_type

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            "timestamp": self.timestamp,
            "backup_path": str(self.backup_path),
            "source_path": str(self.source_path),
            "file_count": self.file_count,
            "total_size_bytes": self.total_size_bytes,
            "total_size_mb": round(self.total_size_bytes / (1024 * 1024), 2),
            "backup_type": self.backup_type,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackupMetadata":
        """Create metadata from dictionary."""
        return cls(
            timestamp=data["timestamp"],
            backup_path=Path(data["backup_path"]),
            source_path=Path(data["source_path"]),
            file_count=data["file_count"],
            total_size_bytes=data["total_size_bytes"],
            backup_type=data.get("backup_type", "manual"),
        )


class BackupManager:
    """Manages backups and restores for Searchat data."""

    METADATA_FILE = "backup_metadata.json"

    def __init__(self, data_dir: Path, backup_dir: Path | None = None):
        """
        Initialize backup manager.

        Args:
            data_dir: Path to the searchat data directory (e.g., ~/.searchat)
            backup_dir: Optional custom backup directory. Defaults to data_dir/backups
        """
        self.data_dir = Path(data_dir)

        if backup_dir:
            self.backup_dir = Path(backup_dir)
        else:
            # Default: .searchat/backups/
            self.backup_dir = self.data_dir / "backups"

        # Ensure backup directory exists
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def _get_directory_size(self, path: Path) -> int:
        """Calculate total size of all files in a directory."""
        total = 0
        for item in path.rglob("*"):
            if item.is_file():
                total += item.stat().st_size
        return total

    def _write_manifest(self, backup_path: Path, manifest: BackupManifest) -> None:
        manifest_path = backup_path / BACKUP_MANIFEST_FILE
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest.to_dict(), f, indent=2)

    def _load_manifest(self, backup_path: Path) -> BackupManifest | None:
        manifest_path = backup_path / BACKUP_MANIFEST_FILE
        if not manifest_path.exists():
            return None
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return BackupManifest.from_dict(data)

    def _copy_tree_with_manifest(
        self,
        source_root: Path,
        dest_root: Path,
        *,
        relative_prefix: str,
        manifest_files: dict[str, dict[str, object]],
    ) -> tuple[int, int]:
        file_count = 0
        total_size = 0
        for src in source_root.rglob("*"):
            if not src.is_file():
                continue
            rel_inside = src.relative_to(source_root)
            dest = dest_root / rel_inside
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

            file_count += 1
            st = dest.stat()
            total_size += st.st_size

            rel_key = str(Path(relative_prefix) / rel_inside).replace("\\", "/")
            sha = _sha256_file(dest)
            manifest_files[rel_key] = {
                "content_sha256": sha,
                "stored_sha256": sha,
                "stored_rel_path": rel_key,
                "size_bytes": int(st.st_size),
                "mtime_epoch": float(st.st_mtime),
            }
        return file_count, total_size

    def resolve_backup_chain(self, backup_name: str, *, max_chain_length: int = 10) -> list[str]:
        """Resolve ancestry chain from base full backup to target.

        Chain length counts total entries including the base full backup.
        """
        chain: list[str] = []
        seen: set[str] = set()
        current = backup_name
        while True:
            if current in seen:
                raise ValueError("Backup chain contains a cycle")
            seen.add(current)
            chain.append(current)
            if len(chain) > max_chain_length:
                raise ValueError(f"Backup chain length exceeds max ({max_chain_length})")

            current_path = self.backup_dir / current
            if not current_path.exists() or not current_path.is_dir():
                raise ValueError(f"Backup not found in chain: {current}")
            manifest = self._load_manifest(current_path)
            if manifest is None or not manifest.parent_name:
                break
            current = manifest.parent_name

        chain.reverse()
        return chain

    def validate_backup_artifact(
        self,
        backup_name: str,
        *,
        verify_hashes: bool = False,
        max_chain_length: int = 10,
    ) -> dict[str, object]:
        """Validate backup manifests, chain, and optional file hashes.

        This is separate from validate_backup(), which checks snapshot-browsable structure.
        """
        errors: list[str] = []

        backup_path = self.backup_dir / backup_name
        if not backup_path.exists() or not backup_path.is_dir():
            return {
                "backup_name": backup_name,
                "valid": False,
                "errors": [f"Backup not found: {backup_name}"],
            }

        manifest = self._load_manifest(backup_path)
        if manifest is None:
            # Older backups: structural checks only.
            if verify_hashes:
                errors.append("Backup manifest missing")
            structural_ok = self.validate_backup(backup_path)
            return {
                "backup_name": backup_name,
                "backup_mode": "full",
                "encrypted": False,
                "parent_name": None,
                "chain_length": 1,
                "snapshot_browsable": structural_ok,
                "has_manifest": False,
                "valid": structural_ok and not errors,
                "errors": errors,
            }

        try:
            chain = self.resolve_backup_chain(backup_name, max_chain_length=max_chain_length)
        except Exception as e:
            return {
                "backup_name": backup_name,
                "backup_mode": manifest.backup_mode,
                "encrypted": bool(manifest.encrypted),
                "parent_name": manifest.parent_name,
                "has_manifest": True,
                "valid": False,
                "errors": [str(e)],
            }

        chain_manifests: list[tuple[str, BackupManifest]] = []
        for name in chain:
            m = self._load_manifest(self.backup_dir / name)
            if m is None:
                errors.append(f"Backup manifest missing: {name}")
                continue
            chain_manifests.append((name, m))

        if chain_manifests:
            base_name, base_manifest = chain_manifests[0]
            if base_manifest.backup_mode != "full":
                errors.append(f"Backup chain base must be full: {base_name}")
        else:
            errors.append("Backup chain has no manifests")

        encrypted = bool(manifest.encrypted)
        if any(bool(m.encrypted) != encrypted for _, m in chain_manifests):
            errors.append("Mixed encrypted/plaintext backup chains are not supported")

        if verify_hashes:
            for name, m in chain_manifests:
                bpath = self.backup_dir / name
                for rel_path, meta in m.files.items():
                    stored_rel = meta.get("stored_rel_path") or rel_path
                    if not isinstance(stored_rel, str) or not stored_rel:
                        errors.append(f"Invalid stored_rel_path for {rel_path} in {name}")
                        continue

                    expected = meta.get("stored_sha256") or meta.get("sha256")
                    if not isinstance(expected, str) or not expected:
                        errors.append(f"Invalid stored sha256 for {rel_path} in {name}")
                        continue

                    fpath = bpath / Path(stored_rel)
                    if not fpath.exists() or not fpath.is_file():
                        errors.append(f"Missing file {stored_rel} in {name}")
                        continue
                    actual = _sha256_file(fpath)
                    if actual != expected:
                        errors.append(f"Hash mismatch for {rel_path} in {name}")

        snapshot_browsable = False
        if manifest.backup_mode == "full" and not manifest.encrypted:
            snapshot_browsable = self.validate_backup(backup_path)

        return {
            "backup_name": backup_name,
            "backup_mode": manifest.backup_mode,
            "encrypted": bool(manifest.encrypted),
            "parent_name": manifest.parent_name,
            "chain_length": len(chain),
            "snapshot_browsable": snapshot_browsable,
            "has_manifest": True,
            "valid": not errors,
            "errors": errors,
        }

    def get_backup_summary(self, backup_name: str) -> dict[str, object]:
        backup_path = self.backup_dir / backup_name
        manifest = self._load_manifest(backup_path)

        backup_mode = "full"
        encrypted = False
        parent_name: str | None = None
        chain_length = 1

        if manifest is not None:
            backup_mode = manifest.backup_mode
            encrypted = bool(manifest.encrypted)
            parent_name = manifest.parent_name
            try:
                chain_length = len(self.resolve_backup_chain(backup_name))
            except Exception:
                chain_length = 0
        else:
            # Older backups without a manifest are treated as plaintext full backups.
            backup_mode = "full"
            encrypted = False
            parent_name = None
            chain_length = 1

        snapshot_browsable = False
        if backup_mode == "full" and not encrypted:
            try:
                snapshot_browsable = self.validate_backup(backup_path)
            except Exception:
                snapshot_browsable = False

        return {
            "name": backup_name,
            "backup_mode": backup_mode,
            "encrypted": encrypted,
            "parent_name": parent_name,
            "chain_length": chain_length,
            "snapshot_browsable": snapshot_browsable,
            "has_manifest": manifest is not None,
        }

    def _count_files(self, path: Path) -> int:
        """Count all files in a directory."""
        return sum(1 for item in path.rglob("*") if item.is_file())

    def _iter_live_backup_files(self) -> list[tuple[str, Path]]:
        """Return (relative_path, absolute_path) for all files in backup scope."""
        items_to_backup: list[tuple[str, Path]] = [
            ("data", self.data_dir / "data"),
            ("config", self.data_dir / "config"),
        ]
        files: list[tuple[str, Path]] = []
        for prefix, root in items_to_backup:
            if not root.exists():
                continue
            if root.is_file():
                files.append((prefix, root))
                continue
            for src in root.rglob("*"):
                if not src.is_file():
                    continue
                rel_key = str(Path(prefix) / src.relative_to(root)).replace("\\", "/")
                files.append((rel_key, src))
        return files

    def _effective_state_from_chain(self, chain: list[str]) -> dict[str, str]:
        """Compute effective file sha map for a chain.

        The returned mapping is relative_path -> sha256.

        Notes:
        - Requires manifests for all backups in the chain.
        - Uses content hashes, so it works for encrypted chains.
        """
        if not chain:
            raise ValueError("Empty backup chain")

        state: dict[str, str] = {}
        for idx, name in enumerate(chain):
            backup_path = self.backup_dir / name
            manifest = self._load_manifest(backup_path)
            if manifest is None:
                raise ValueError(f"Backup manifest missing: {name}")
            if idx == 0 and manifest.backup_mode != "full":
                raise ValueError("Backup chain base must be a full backup")

            for rel_path in manifest.deleted_files:
                state.pop(rel_path, None)

            for rel_path, meta in manifest.files.items():
                sha = meta.get("content_sha256") or meta.get("sha256")
                if not isinstance(sha, str) or not sha:
                    raise ValueError(f"Invalid sha256 for {rel_path} in {name}")
                state[rel_path] = sha

        return state

    def create_incremental_backup(
        self,
        *,
        parent_name: str,
        backup_name: str | None = None,
        backup_type: str = "manual",
        encrypted: bool = False,
        max_chain_length: int = 10,
    ) -> BackupMetadata:
        """Create an incremental (delta) backup using parent chain manifests.

        Chain length counts total entries including the base full backup.
        """
        parent_chain = self.resolve_backup_chain(parent_name, max_chain_length=max_chain_length)
        if len(parent_chain) + 1 > max_chain_length:
            raise ValueError(f"Backup chain length exceeds max ({max_chain_length})")

        for name in parent_chain:
            m = self._load_manifest(self.backup_dir / name)
            if m is None:
                raise ValueError(f"Backup manifest missing: {name}")
            if bool(m.encrypted) != encrypted:
                raise ValueError("Encrypted flag must match parent chain")

        # Ensure we can compute parent effective state.
        parent_state = self._effective_state_from_chain(parent_chain)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if backup_name:
            folder_name = f"{backup_name}_{timestamp}"
        else:
            folder_name = f"incremental_{timestamp}"
        backup_path = self.backup_dir / folder_name
        backup_path.mkdir(parents=True, exist_ok=True)

        (backup_path / "data").mkdir(parents=True, exist_ok=True)
        (backup_path / "config").mkdir(parents=True, exist_ok=True)

        key: bytes | None = None
        if encrypted:
            key = get_backup_key()

        live_files = self._iter_live_backup_files()

        live_state: dict[str, str] = {}
        changed_files: list[tuple[str, Path, str]] = []
        for rel_key, src in live_files:
            sha = _sha256_file(src)
            live_state[rel_key] = sha
            if parent_state.get(rel_key) != sha:
                changed_files.append((rel_key, src, sha))

        deleted_files = sorted(set(parent_state.keys()) - set(live_state.keys()))

        file_count = 0
        total_size = 0
        manifest_files: dict[str, dict[str, object]] = {}

        for rel_key, src, sha in changed_files:
            st = src.stat()
            if encrypted:
                stored_rel = f"{rel_key}.enc"
                content_sha, stored_sha, stored_size = encrypt_file(src, backup_path / stored_rel, key=cast(bytes, key))
                if content_sha != sha:
                    raise RuntimeError("Content hash mismatch during encryption")
            else:
                stored_rel = rel_key
                dest = backup_path / Path(rel_key)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                stored_size = int(dest.stat().st_size)
                stored_sha = sha
                content_sha = sha

            file_count += 1
            total_size += int(stored_size)
            manifest_files[rel_key] = {
                "content_sha256": content_sha,
                "stored_sha256": stored_sha,
                "stored_rel_path": stored_rel,
                "size_bytes": int(stored_size),
                "mtime_epoch": float(st.st_mtime),
            }

        metadata = BackupMetadata(
            timestamp=timestamp,
            backup_path=backup_path,
            source_path=self.data_dir,
            file_count=file_count,
            total_size_bytes=total_size,
            backup_type=backup_type,
        )

        metadata_path = backup_path / self.METADATA_FILE
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata.to_dict(), f, indent=2)

        manifest = BackupManifest(
            manifest_version=1,
            backup_mode="incremental",
            encrypted=encrypted,
            created_at=datetime.now().isoformat(),
            parent_name=parent_name,
            files=manifest_files,
            deleted_files=deleted_files,
        )
        self._write_manifest(backup_path, manifest)

        return metadata

    def materialize_backup(
        self,
        *,
        backup_name: str,
        dest_dir: Path,
        verify_hashes: bool = True,
        max_chain_length: int = 10,
    ) -> None:
        """Materialize a backup chain into a plaintext dataset directory."""
        if dest_dir.exists() and any(dest_dir.iterdir()):
            raise ValueError(f"Destination directory is not empty: {dest_dir}")
        dest_dir.mkdir(parents=True, exist_ok=True)

        chain = self.resolve_backup_chain(backup_name, max_chain_length=max_chain_length)
        if not chain:
            raise ValueError("Empty backup chain")

        base_manifest = self._load_manifest(self.backup_dir / chain[0])
        if base_manifest is None:
            raise ValueError(f"Backup manifest missing: {chain[0]}")
        if base_manifest.backup_mode != "full":
            raise ValueError("Backup chain base must be a full backup")
        manifests: list[tuple[str, BackupManifest]] = []
        for name in chain:
            backup_path = self.backup_dir / name
            manifest = self._load_manifest(backup_path)
            if manifest is None:
                raise ValueError(f"Backup manifest missing: {name}")
            manifests.append((name, manifest))

        encrypted = bool(manifests[-1][1].encrypted)
        if any(bool(m.encrypted) != encrypted for _, m in manifests):
            raise ValueError("Mixed encrypted/plaintext backup chains are not supported")

        key: bytes | None = None
        if encrypted:
            key = get_backup_key()

        for name, manifest in manifests:
            backup_path = self.backup_dir / name

            # Apply file overlays.
            for rel_path, meta in manifest.files.items():
                stored_rel = meta.get("stored_rel_path") or rel_path
                if not isinstance(stored_rel, str) or not stored_rel:
                    raise ValueError(f"Invalid stored_rel_path for {rel_path} in {name}")

                src = backup_path / Path(stored_rel)
                if not src.exists() or not src.is_file():
                    raise FileNotFoundError(f"Backup file missing: {src}")
                dst = dest_dir / Path(rel_path)
                dst.parent.mkdir(parents=True, exist_ok=True)

                content_expected = meta.get("content_sha256") or meta.get("sha256")
                stored_expected = meta.get("stored_sha256") or meta.get("sha256")
                if not isinstance(content_expected, str) or not content_expected:
                    raise ValueError(f"Invalid sha256 for {rel_path} in {name}")
                if not isinstance(stored_expected, str) or not stored_expected:
                    raise ValueError(f"Invalid stored sha256 for {rel_path} in {name}")

                if verify_hashes:
                    stored_actual = _sha256_file(src)
                    if stored_actual != stored_expected:
                        raise ValueError(f"Stored hash mismatch for {rel_path} in {name}")

                if encrypted:
                    decrypt_file(src, dst, key=cast(bytes, key))
                    if verify_hashes:
                        content_actual = _sha256_file(dst)
                        if content_actual != content_expected:
                            raise ValueError(f"Content hash mismatch for {rel_path} in {name}")
                else:
                    shutil.copy2(src, dst)
                    if verify_hashes:
                        content_actual = _sha256_file(dst)
                        if content_actual != content_expected:
                            raise ValueError(f"Hash mismatch for {rel_path} in {name}")

            # Apply deletions.
            for rel_path in manifest.deleted_files:
                target = dest_dir / Path(rel_path)
                if not target.exists():
                    continue
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()

    def create_backup(
        self,
        backup_name: str | None = None,
        backup_type: str = "manual",
        *,
        encrypted: bool = False,
    ) -> BackupMetadata:
        """
        Create a backup of the current index and data.

        Args:
            backup_name: Optional custom backup name. If not provided, uses timestamp.
            backup_type: Type of backup (manual, pre_restore, scheduled)

        Returns:
            BackupMetadata object with backup information

        Raises:
            FileNotFoundError: If data directory doesn't exist
            IOError: If backup creation fails
        """
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {self.data_dir}")

        # Generate backup name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if backup_name:
            folder_name = f"{backup_name}_{timestamp}"
        else:
            folder_name = f"backup_{timestamp}"

        backup_path = self.backup_dir / folder_name

        logger.info(f"Creating backup: {backup_path}")

        # Create backup directory
        backup_path.mkdir(parents=True, exist_ok=True)

        (backup_path / "data").mkdir(parents=True, exist_ok=True)
        (backup_path / "config").mkdir(parents=True, exist_ok=True)

        key: bytes | None = None
        if encrypted:
            key = get_backup_key()

        files = self._iter_live_backup_files()

        file_count = 0
        total_size = 0
        manifest_files: dict[str, dict[str, object]] = {}

        for rel_key, src in files:
            st = src.stat()
            if encrypted:
                logger.info(f"  Encrypting file: {rel_key}")
                stored_rel = f"{rel_key}.enc"
                content_sha, stored_sha, stored_size = encrypt_file(src, backup_path / stored_rel, key=cast(bytes, key))
            else:
                # Copy plaintext.
                dest = backup_path / Path(rel_key)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                stored_rel = rel_key
                stored_size = int(dest.stat().st_size)
                content_sha = _sha256_file(dest)
                stored_sha = content_sha

            file_count += 1
            total_size += int(stored_size)
            manifest_files[rel_key] = {
                "content_sha256": content_sha,
                "stored_sha256": stored_sha,
                "stored_rel_path": stored_rel,
                "size_bytes": int(stored_size),
                "mtime_epoch": float(st.st_mtime),
            }

        # Create metadata
        metadata = BackupMetadata(
            timestamp=timestamp,
            backup_path=backup_path,
            source_path=self.data_dir,
            file_count=file_count,
            total_size_bytes=total_size,
            backup_type=backup_type,
        )

        # Save metadata to backup directory
        metadata_path = backup_path / self.METADATA_FILE
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata.to_dict(), f, indent=2)

        # Save manifest (new backups always include it).
        manifest = BackupManifest(
            manifest_version=1,
            backup_mode="full",
            encrypted=encrypted,
            created_at=datetime.now().isoformat(),
            parent_name=None,
            files=manifest_files,
            deleted_files=[],
        )
        self._write_manifest(backup_path, manifest)

        logger.info(
            f"Backup created: {folder_name} "
            f"({file_count} files, {metadata.to_dict()['total_size_mb']} MB)"
        )

        return metadata

    def list_backups(self) -> list[BackupMetadata]:
        """
        List all available backups.

        Returns:
            List of BackupMetadata objects, sorted by timestamp (newest first)
        """
        backups = []

        if not self.backup_dir.exists():
            return backups

        for backup_path in self.backup_dir.iterdir():
            if not backup_path.is_dir():
                continue

            metadata_path = backup_path / self.METADATA_FILE

            if metadata_path.exists():
                # Load from metadata file
                try:
                    with open(metadata_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    backups.append(BackupMetadata.from_dict(data))
                except Exception as e:
                    logger.warning(f"Failed to load backup metadata from {metadata_path}: {e}")
            else:
                # Create metadata on-the-fly for older backups without metadata
                try:
                    file_count = self._count_files(backup_path)
                    total_size = self._get_directory_size(backup_path)

                    # Extract timestamp from folder name
                    folder_name = backup_path.name
                    if "_" in folder_name:
                        timestamp = folder_name.rsplit("_", 1)[-1]
                    else:
                        timestamp = datetime.fromtimestamp(
                            backup_path.stat().st_mtime
                        ).strftime("%Y%m%d_%H%M%S")

                    backups.append(BackupMetadata(
                        timestamp=timestamp,
                        backup_path=backup_path,
                        source_path=self.data_dir,
                        file_count=file_count,
                        total_size_bytes=total_size,
                        backup_type="unknown",
                    ))
                except Exception as e:
                    logger.warning(f"Failed to analyze backup at {backup_path}: {e}")

        # Sort by timestamp (newest first)
        backups.sort(key=lambda b: b.timestamp, reverse=True)

        return backups

    def validate_backup(self, backup_path: Path) -> bool:
        """
        Validate that a backup has the expected structure.

        Args:
            backup_path: Path to the backup directory

        Returns:
            True if backup is valid, False otherwise
        """
        if not backup_path.exists() or not backup_path.is_dir():
            logger.error(f"Backup path does not exist or is not a directory: {backup_path}")
            return False

        # Check for essential directories
        data_dir = backup_path / "data"

        if not data_dir.exists():
            logger.error(f"Backup missing data directory: {data_dir}")
            return False

        # Check for parquet files (the critical data).
        # Historical note: older validation expected parquets directly under data/.
        # Current index layout stores parquets under data/conversations/.
        parquet_files = list(data_dir.glob("*.parquet"))
        if not parquet_files:
            parquet_files = list((data_dir / "conversations").glob("*.parquet"))
        if not parquet_files:
            logger.error(
                "Backup contains no parquet files in: %s or %s",
                data_dir,
                data_dir / "conversations",
            )
            return False

        logger.debug(f"Backup validation passed: {backup_path.name}")
        return True

    def restore_from_backup(
        self,
        backup_path: Path,
        create_pre_restore_backup: bool = True,
        verify_hashes: bool = True,
    ) -> BackupMetadata | None:
        """
        Restore data from a backup.

        SAFETY:
        - Creates a pre-restore backup by default
        - Validates backup structure before restoring
        - Uses atomic copy operations

        Args:
            backup_path: Path to the backup directory to restore from
            create_pre_restore_backup: Create a backup before restoring (recommended)

        Returns:
            Metadata of the pre-restore backup (if created)

        Raises:
            FileNotFoundError: If backup doesn't exist
            ValueError: If backup validation fails
            IOError: If restore operation fails
        """
        backup_path = Path(backup_path)

        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_path}")

        manifest = self._load_manifest(backup_path)

        if manifest is not None:
            res = self.validate_backup_artifact(
                backup_path.name,
                verify_hashes=verify_hashes,
            )
            if not res.get("valid"):
                errors = res.get("errors")
                raise ValueError(f"Backup validation failed: {errors}")
        else:
            # Older backups: structural checks only.
            if not self.validate_backup(backup_path):
                raise ValueError(f"Backup validation failed: {backup_path}")

        # Create pre-restore backup
        pre_restore_metadata = None
        if create_pre_restore_backup and self.data_dir.exists():
            logger.info("Creating pre-restore backup...")
            pre_restore_metadata = self.create_backup(
                backup_name="pre_restore",
                backup_type="pre_restore"
            )

        logger.info(f"Restoring from backup: {backup_path}")

        source_root = backup_path
        temp_dir_cm: tempfile.TemporaryDirectory[str] | None = None

        try:
            if manifest is not None and (manifest.backup_mode != "full" or manifest.encrypted):
                # Materialize into a staging directory, then restore from it.
                backup_name = backup_path.name
                temp_dir_cm = tempfile.TemporaryDirectory(prefix="searchat_materialize_", dir=str(self.backup_dir))
                staging_root = Path(temp_dir_cm.name)
                self.materialize_backup(
                    backup_name=backup_name,
                    dest_dir=staging_root,
                    verify_hashes=verify_hashes,
                )
                source_root = staging_root

            # Restore items
            items_to_restore = [
                ("data", source_root / "data", self.data_dir / "data"),
                ("config", source_root / "config", self.data_dir / "config"),
            ]

            for item_name, source, dest in items_to_restore:
                if not source.exists():
                    logger.warning(f"Backup missing {item_name}, skipping")
                    continue

                # Remove existing destination
                if dest.exists():
                    logger.info(f"  Removing existing {item_name}")
                    if dest.is_dir():
                        shutil.rmtree(dest)
                    else:
                        dest.unlink()

                # Copy from backup
                logger.info(f"  Restoring {item_name}")
                if source.is_dir():
                    shutil.copytree(source, dest)
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, dest)
        finally:
            if temp_dir_cm is not None:
                temp_dir_cm.cleanup()

        logger.info(f"Restore complete from: {backup_path.name}")

        return pre_restore_metadata

    def delete_backup(self, backup_path: Path) -> None:
        """
        Delete a backup directory.

        Args:
            backup_path: Path to the backup directory to delete

        Raises:
            FileNotFoundError: If backup doesn't exist
        """
        backup_path = Path(backup_path)

        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_path}")

        logger.info(f"Deleting backup: {backup_path}")
        shutil.rmtree(backup_path)
        logger.info(f"Backup deleted: {backup_path.name}")
