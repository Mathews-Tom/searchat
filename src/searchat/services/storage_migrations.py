"""Migration helpers for persisted storage metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from searchat.config.constants import INDEX_METADATA_FILENAME
from searchat.services.storage_contracts import IndexMetadata, read_index_metadata, write_index_metadata


@dataclass(frozen=True)
class MetadataMigrationPlan:
    original: IndexMetadata
    migrated: IndexMetadata
    changed_fields: tuple[str, ...]

    @property
    def has_changes(self) -> bool:
        return bool(self.changed_fields)


def plan_index_metadata_migration(
    metadata: IndexMetadata,
    *,
    embedding_model: str | None = None,
) -> MetadataMigrationPlan:
    migrated = metadata.normalized(embedding_model=embedding_model)
    changed = tuple(
        field
        for field in metadata.to_dict().keys()
        if metadata.to_dict().get(field) != migrated.to_dict().get(field)
    )
    return MetadataMigrationPlan(original=metadata, migrated=migrated, changed_fields=changed)


def read_raw_index_metadata(search_dir: Path) -> dict:
    metadata_path = search_dir / "data" / "indices" / INDEX_METADATA_FILENAME
    with open(metadata_path, "r", encoding="utf-8") as f:
        return json.load(f)


def migrate_index_metadata_file(
    search_dir: Path,
    *,
    embedding_model: str | None = None,
    apply: bool = False,
) -> MetadataMigrationPlan:
    metadata = read_index_metadata(search_dir)
    plan = plan_index_metadata_migration(metadata, embedding_model=embedding_model)
    if apply and plan.has_changes:
        write_index_metadata(search_dir, plan.migrated)
    return plan
