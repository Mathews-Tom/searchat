"""Round-trip export/re-parse tests for `VibeConnector.export_original` (M8).

Exercises `export_original` only via `services.source_lifecycle.verify_roundtrip`
against a real parsed `ConversationRecord` -- never a hand-constructed one --
so these tests actually prove the reversibility guarantee that gates
archive/prune, not just that `export_original` returns *some* bytes.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from searchat.core.connectors.vibe import VibeConnector
from searchat.services.source_lifecycle import verify_roundtrip


@pytest.fixture
def connector() -> VibeConnector:
    return VibeConnector()


def _write_session(
    tmp_path: Path,
    name: str,
    session_id: str,
    messages: list[dict],
    working_directory: str | None = "",
) -> Path:
    """Write a native Vibe session JSON.

    `working_directory=None` omits the key entirely (the "absent" case);
    `working_directory=""` writes it as an empty string (the "empty" case).
    Both make `VibeConnector.parse` fall back to the `vibe-session` project
    basename.
    """
    environment: dict[str, str] = {}
    if working_directory is not None:
        environment["working_directory"] = working_directory
    payload = {
        "metadata": {
            "session_id": session_id,
            "environment": environment,
            "start_time": "2026-01-15T10:00:00",
            "end_time": "2026-01-15T10:45:00",
        },
        "messages": messages,
    }
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class TestVibeExportOriginalRoundtrip:
    def test_roundtrip_with_working_directory(self, connector: VibeConnector, tmp_path: Path) -> None:
        messages = [
            {"role": "user", "content": "How do I fix this bug in the parser?"},
            {"role": "assistant", "content": "Let's look at the parser module and add a null check."},
        ]
        path = _write_session(
            tmp_path,
            "session.json",
            "vibe-session-abc123",
            messages,
            working_directory="/home/x/somerepo",
        )

        record = connector.parse(path, embedding_id=1)
        assert record.project_id == "vibe-somerepo"
        assert record.message_count == 2

        result = verify_roundtrip(connector, record)

        assert result.ok is True
        assert result.mismatches == ()
        assert result.reason is None

        exported = connector.export_original(record)
        assert isinstance(exported, bytes)
        assert len(exported) > 0

    def test_roundtrip_without_working_directory(self, connector: VibeConnector, tmp_path: Path) -> None:
        messages = [
            {"role": "user", "content": "What does this function do?"},
            {"role": "assistant", "content": "It parses the input and returns a list of tokens."},
        ]
        path = _write_session(
            tmp_path,
            "session2.json",
            "vibe-session-def456",
            messages,
            working_directory=None,
        )

        record = connector.parse(path, embedding_id=2)
        assert record.project_id == "vibe-vibe-session"
        assert record.message_count == 2

        result = verify_roundtrip(connector, record)

        assert result.ok is True
        assert result.mismatches == ()
        assert result.reason is None
