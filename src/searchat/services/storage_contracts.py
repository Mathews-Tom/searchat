"""Typed storage contracts for index and backup metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from searchat.config.constants import (
    INDEX_FORMAT,
    INDEX_FORMAT_VERSION,
    INDEX_SCHEMA_VERSION,
    INDEX_METADATA_FILENAME,
)


BACKUP_MANIFEST_FILE = "backup_manifest.json"
BACKUP_METADATA_FILE = "backup_metadata.json"
BACKUP_MANIFEST_VERSION = 1
BACKUP_METADATA_VERSION = 1


class StorageCompatibilityError(ValueError):
    """Raised when persisted storage artifacts are incompatible."""


@dataclass(frozen=True)
class IndexMetadata:
    schema_version: str
    index_format_version: str
    created_at: str
    embedding_model: str
    format: str
    last_updated: str | None = None
    total_conversations: int = 0
    total_chunks: int = 0
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    next_vector_id: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "index_format_version": self.index_format_version,
            "created_at": self.created_at,
            "embedding_model": self.embedding_model,
            "format": self.format,
            "last_updated": self.last_updated,
            "total_conversations": self.total_conversations,
            "total_chunks": self.total_chunks,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "next_vector_id": self.next_vector_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IndexMetadata":
        return cls(
            schema_version=str(data.get("schema_version", "")),
            index_format_version=str(data.get("index_format_version", "")),
            created_at=str(data.get("created_at", "")),
            embedding_model=str(data.get("embedding_model", "")),
            format=str(data.get("format", "")),
            last_updated=None if data.get("last_updated") is None else str(data.get("last_updated")),
            total_conversations=int(data.get("total_conversations", 0)),
            total_chunks=int(data.get("total_chunks", 0)),
            chunk_size=None if data.get("chunk_size") is None else int(data.get("chunk_size")),
            chunk_overlap=None if data.get("chunk_overlap") is None else int(data.get("chunk_overlap")),
            next_vector_id=int(data.get("next_vector_id", 0)),
        )

    def validate_compatible(self, *, embedding_model: str | None = None) -> None:
        if embedding_model is not None and self.embedding_model != embedding_model:
            raise StorageCompatibilityError(
                f"Model mismatch: index uses '{self.embedding_model}', "
                f"config specifies '{embedding_model}'. Rebuild index with correct model."
            )
        if self.format != INDEX_FORMAT:
            raise StorageCompatibilityError(
                f"Index format mismatch: index uses '{self.format}', "
                f"expected '{INDEX_FORMAT}'. Rebuild index required."
            )
        if self.schema_version != INDEX_SCHEMA_VERSION:
            raise StorageCompatibilityError(
                f"Schema version mismatch: index uses version {self.schema_version}, "
                f"expected version {INDEX_SCHEMA_VERSION}. Rebuild index required."
            )
        if self.index_format_version != INDEX_FORMAT_VERSION:
            raise StorageCompatibilityError(
                f"Index format version mismatch: index uses version {self.index_format_version}, "
                f"expected version {INDEX_FORMAT_VERSION}. Rebuild index required."
            )

    def normalized(self, *, embedding_model: str | None = None) -> "IndexMetadata":
        model_name = self.embedding_model or (embedding_model or "")
        last_updated = self.last_updated or self.created_at
        chunk_size = self.chunk_size if self.chunk_size is not None else 1500
        chunk_overlap = self.chunk_overlap if self.chunk_overlap is not None else 200
        next_vector_id = self.next_vector_id
        if next_vector_id == 0 and self.total_chunks > 0:
            next_vector_id = self.total_chunks
        return IndexMetadata(
            schema_version=self.schema_version,
            index_format_version=self.index_format_version,
            created_at=self.created_at,
            embedding_model=model_name,
            format=self.format,
            last_updated=last_updated,
            total_conversations=self.total_conversations,
            total_chunks=self.total_chunks,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            next_vector_id=next_vector_id,
        )


def index_metadata_path(dataset_root: Path) -> Path:
    return dataset_root / "data" / "indices" / INDEX_METADATA_FILENAME


def read_index_metadata_root(dataset_root: Path) -> IndexMetadata:
    metadata_path = index_metadata_path(dataset_root)
    if not metadata_path.exists():
        raise FileNotFoundError(
            f"Index metadata not found at {metadata_path}. "
            "Index format outdated, rebuild required. Run indexer."
        )
    with open(metadata_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return IndexMetadata.from_dict(cast(dict[str, Any], data))


def read_index_metadata(search_dir: Path) -> IndexMetadata:
    return read_index_metadata_root(search_dir)


def write_index_metadata_root(dataset_root: Path, metadata: IndexMetadata) -> None:
    metadata_path = index_metadata_path(dataset_root)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata.to_dict(), f, indent=2)


def write_index_metadata(search_dir: Path, metadata: IndexMetadata) -> None:
    write_index_metadata_root(search_dir, metadata)


@dataclass(frozen=True)
class BackupManifest:
    manifest_version: int
    backup_mode: str
    encrypted: bool
    created_at: str
    parent_name: str | None
    files: dict[str, dict[str, object]]
    deleted_files: list[str]

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
        manifest_version = int(data.get("manifest_version", BACKUP_MANIFEST_VERSION))
        if manifest_version != BACKUP_MANIFEST_VERSION:
            raise StorageCompatibilityError(
                f"Backup manifest version mismatch: artifact uses version {manifest_version}, "
                f"expected version {BACKUP_MANIFEST_VERSION}."
            )
        parent = data.get("parent_name")
        parent_name = None if parent is None else str(parent)
        return cls(
            manifest_version=manifest_version,
            backup_mode=str(data.get("backup_mode", "full")),
            encrypted=bool(data.get("encrypted", False)),
            created_at=str(data.get("created_at", "")),
            parent_name=parent_name,
            files=cast(dict[str, dict[str, object]], data.get("files", {})),
            deleted_files=list(data.get("deleted_files", [])),
        )


@dataclass(frozen=True)
class BackupMetadata:
    timestamp: str
    backup_path: Path
    source_path: Path
    file_count: int
    total_size_bytes: int
    backup_type: str = "manual"
    metadata_version: int = BACKUP_METADATA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata_version": self.metadata_version,
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
        metadata_version = int(data.get("metadata_version", BACKUP_METADATA_VERSION))
        if metadata_version != BACKUP_METADATA_VERSION:
            raise StorageCompatibilityError(
                f"Backup metadata version mismatch: artifact uses version {metadata_version}, "
                f"expected version {BACKUP_METADATA_VERSION}."
            )
        return cls(
            timestamp=str(data["timestamp"]),
            backup_path=Path(data["backup_path"]),
            source_path=Path(data["source_path"]),
            file_count=int(data["file_count"]),
            total_size_bytes=int(data["total_size_bytes"]),
            backup_type=str(data.get("backup_type", "manual")),
            metadata_version=metadata_version,
        )

    def normalized(self) -> "BackupMetadata":
        return BackupMetadata(
            timestamp=self.timestamp,
            backup_path=self.backup_path,
            source_path=self.source_path,
            file_count=self.file_count,
            total_size_bytes=self.total_size_bytes,
            backup_type=self.backup_type,
            metadata_version=BACKUP_METADATA_VERSION,
        )
