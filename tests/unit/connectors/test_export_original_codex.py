"""Round-trip tests for `CodexConnector.export_original` via
`services.source_lifecycle.verify_roundtrip` (M8).

Writes a real Codex-format `.jsonl` fixture (a `session_meta` line followed
by bare `{role, content, timestamp}` lines), parses it with the real
connector, and feeds the resulting `ConversationRecord` through the real
`verify_roundtrip` -- no mocking of `connector.parse`,
`connector.export_original`, or `verify_roundtrip` itself.
"""
from __future__ import annotations

import json

import pytest

from searchat.core.connectors.codex import CodexConnector
from searchat.services.source_lifecycle import verify_roundtrip


@pytest.fixture
def connector() -> CodexConnector:
    return CodexConnector()


class TestCodexExportOriginalRoundtrip:
    def test_roundtrip_session_meta_and_messages(self, connector: CodexConnector, tmp_path) -> None:
        """A session_meta line carrying the session id, followed by a real
        user/assistant exchange, must survive export -> re-parse: the
        `session_meta` line is how `export_original` guarantees
        `conversation_id` recovers exactly regardless of which of Codex's
        on-disk shapes the original file used."""
        session_id = "session-9f3c2a"
        lines = [
            {"type": "session_meta", "payload": {"id": session_id}},
            {
                "role": "user",
                "content": "Please refactor the auth module for clarity.",
                "timestamp": "2026-02-01T09:00:00",
            },
            {
                "role": "assistant",
                "content": "Sure, I split validate_token into two smaller helpers.",
                "timestamp": "2026-02-01T09:00:12",
            },
        ]
        path = tmp_path / "rollout-9f3c2a.jsonl"
        path.write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")

        record = connector.parse(path, embedding_id=3)

        # Sanity: conversation_id came from the session_meta payload, not a
        # path-derived fallback.
        assert record.conversation_id == session_id
        assert record.message_count == 2

        exported = connector.export_original(record)
        assert isinstance(exported, bytes)
        assert exported

        result = verify_roundtrip(connector, record)
        assert result.ok is True, result.reason
        assert result.mismatches == ()
