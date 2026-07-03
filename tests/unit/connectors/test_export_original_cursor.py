"""Unit tests for `CursorConnector.export_original` / round-trip reconstruction (M8).

Cursor is NOT verified via `services.source_lifecycle.verify_roundtrip`:
that helper mirrors `record.file_path` under a throwaway temp directory and
re-parses at the mirrored path, which does not match Cursor's scheme.
`record.file_path` here is a *pseudo path* (`<db_path>.cursor/<composer_id>.json`)
that never exists on disk as a literal file -- `CursorConnector.parse`
decodes it back into a real, shared, per-workspace `state.vscdb` SQLite
file sitting one directory level up. Proving the round trip therefore
means relocating a real SQLite file to a new real path and decoding a
pseudo path built against ITS new location, which is what this module does
directly instead of going through `verify_roundtrip`.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from searchat.core.connectors.cursor import CursorConnector


@pytest.fixture
def connector() -> CursorConnector:
    return CursorConnector()


def _make_vscdb(
    db_path: Path,
    composer_id: str,
    created_at: datetime,
    updated_at: datetime,
    messages: list[tuple[str, str, datetime]],
) -> None:
    """Build a real `state.vscdb`-shaped SQLite file: an `ItemTable(key, value)`
    holding one `composerData:<id>` row and one `bubbleId:<id>` row per
    message, matching the exact shapes `CursorConnector._load_composer` /
    `_load_bubbles` expect -- including `timingInfo.clientEndTime`, without
    which a bubble's timestamp falls back to file mtime and would not
    round-trip.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    try:
        con.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
        bubble_ids = [f"bubble-{i}" for i in range(len(messages))]
        headers: list[dict] = []
        rows: list[tuple[str, str]] = []
        for bubble_id, (role, content, timestamp) in zip(bubble_ids, messages):
            bubble_type = 1 if role == "user" else 2
            headers.append({"bubbleId": bubble_id, "type": bubble_type})
            rows.append(
                (
                    f"bubbleId:{bubble_id}",
                    json.dumps(
                        {
                            "bubbleId": bubble_id,
                            "rawText": content,
                            "timingInfo": {"clientEndTime": round(timestamp.timestamp() * 1000)},
                        }
                    ),
                )
            )
        composer = {
            "composerId": composer_id,
            "createdAt": round(created_at.timestamp() * 1000),
            "lastUpdatedAt": round(updated_at.timestamp() * 1000),
            "fullConversationHeadersOnly": headers,
        }
        rows.insert(0, (f"composerData:{composer_id}", json.dumps(composer)))
        con.executemany("INSERT INTO ItemTable (key, value) VALUES (?, ?)", rows)
        con.commit()
    finally:
        con.close()


def _pseudo_path(db_path: Path, composer_id: str) -> Path:
    return Path(f"{db_path.as_posix()}.cursor/{composer_id}.json")


class TestCursorExportRoundtrip:
    def test_export_then_relocate_preserves_content_not_project_id(
        self, connector: CursorConnector, tmp_path: Path
    ) -> None:
        composer_id = "composer-abc123"
        created_at = datetime(2024, 1, 15, 9, 0, 0)
        updated_at = datetime(2024, 1, 15, 9, 5, 0)
        messages = [
            ("user", "How do I sort a list in Python?", datetime(2024, 1, 15, 9, 0, 0)),
            ("assistant", "Use `sorted(lst)` or `lst.sort()`.", datetime(2024, 1, 15, 9, 1, 0)),
        ]

        original_db_path = tmp_path / "original_workspace" / "state.vscdb"
        _make_vscdb(original_db_path, composer_id, created_at, updated_at, messages)
        record = connector.parse(_pseudo_path(original_db_path, composer_id), embedding_id=0)

        exported = connector.export_original(record)
        assert exported  # non-empty bytes: a real SQLite file

        relocated_db_path = tmp_path / "relocated_workspace" / "state.vscdb"
        relocated_db_path.parent.mkdir(parents=True, exist_ok=True)
        relocated_db_path.write_bytes(exported)
        reparsed = connector.parse(
            _pseudo_path(relocated_db_path, record.conversation_id), embedding_id=0
        )

        assert reparsed.conversation_id == record.conversation_id
        assert reparsed.messages == record.messages
        assert reparsed.title == record.title
        assert reparsed.created_at == record.created_at
        assert reparsed.updated_at == record.updated_at

        # `project_id` is deliberately asserted UNEQUAL, not equal. Per
        # `CursorConnector.export_original`'s docstring: `project_id` is
        # derived by `parse()` from the real `.vscdb` file's OWN
        # filesystem path (`_project_id_from_db_path`), which cannot be
        # reconstructed from `record` alone -- it is recomputed fresh from
        # wherever the exported bytes happen to land. Having relocated the
        # database to a different directory here, that path-derived
        # identity necessarily changes; asserting inequality proves the
        # connector is honest about this documented limitation instead of
        # coincidentally matching.
        assert reparsed.project_id != record.project_id
