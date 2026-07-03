"""Round-trip tests for `ClaudeConnector.export_original` via
`services.source_lifecycle.verify_roundtrip` (M8).

Every test here writes a real Claude-format `.jsonl` fixture to disk,
parses it with the real connector, and feeds the resulting
`ConversationRecord` through the real `verify_roundtrip` -- no mocking of
`connector.parse`, `connector.export_original`, or `verify_roundtrip`
itself. This is the reversibility proof gating future source-file
deletion, so it has to exercise the actual re-serialize -> re-parse ->
compare pipeline, not a stand-in for it.
"""
from __future__ import annotations

import json

import pytest

from searchat.core.connectors.claude import ClaudeConnector
from searchat.services.source_lifecycle import verify_roundtrip


@pytest.fixture
def connector() -> ClaudeConnector:
    return ClaudeConnector()


class TestClaudeExportOriginalRoundtrip:
    def test_roundtrip_with_tool_use_files_mentioned(
        self, connector: ClaudeConnector, tmp_path
    ) -> None:
        """An assistant message whose raw `message.content` mixes a `text`
        block with a `tool_use` block (Edit) must survive export -> re-parse:
        `files_mentioned` is not stored verbatim on `MessageRecord`, so
        `export_original` has to reconstruct synthetic `tool_use` blocks for
        `_extract_file_paths` to recover it identically on re-parse.
        """
        lines = [
            {
                "type": "user",
                "timestamp": "2026-01-05T09:00:00",
                "message": {"content": "Please fix the off-by-one bug in file.py"},
            },
            {
                "type": "assistant",
                "timestamp": "2026-01-05T09:00:07",
                "message": {
                    "content": [
                        {"type": "text", "text": "Fixed it by adjusting the loop bound."},
                        {
                            "type": "tool_use",
                            "name": "Edit",
                            "input": {"file_path": "/some/file.py"},
                        },
                    ],
                },
            },
        ]
        # Claude derives project_id/conversation_id from the parent dir name
        # and file stem, not file content -- use a real-looking parent dir.
        path = tmp_path / "myproject" / "abc123.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")

        record = connector.parse(path, embedding_id=1)

        # Sanity: the fixture actually exercises the files_mentioned round
        # trip path, not a vacuous case with nothing to lose.
        assert record.files_mentioned
        assert record.files_mentioned == ["/some/file.py"]

        exported = connector.export_original(record)
        assert isinstance(exported, bytes)
        assert exported

        result = verify_roundtrip(connector, record)
        assert result.ok is True, result.reason
        assert result.mismatches == ()

    def test_roundtrip_plain_text_only(self, connector: ClaudeConnector, tmp_path) -> None:
        """A simpler conversation with no tool_use blocks at all also
        round-trips cleanly -- the baseline case with nothing to reconstruct
        beyond message text."""
        lines = [
            {
                "type": "user",
                "timestamp": "2026-01-06T14:00:00",
                "message": {"content": "What does this function do?"},
            },
            {
                "type": "assistant",
                "timestamp": "2026-01-06T14:00:03",
                "message": {"content": "It sorts the list in place using quicksort."},
            },
        ]
        path = tmp_path / "otherproject" / "def456.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")

        record = connector.parse(path, embedding_id=2)
        assert record.files_mentioned is None

        result = verify_roundtrip(connector, record)
        assert result.ok is True, result.reason
        assert result.mismatches == ()
