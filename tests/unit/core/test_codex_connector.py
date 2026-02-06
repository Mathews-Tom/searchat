from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

from searchat.config.path_resolver import PathResolver
from searchat.core.connectors.codex import CodexConnector


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def test_codex_discovers_and_parses_rollout_envelope(monkeypatch, tmp_path: Path) -> None:
    codex_root = tmp_path / ".codex"
    rollout = codex_root / "sessions" / "2026" / "02" / "06" / "rollout-1234.jsonl"

    _write_jsonl(
        rollout,
        [
            {
                "timestamp": "2026-02-06T07:11:42.272Z",
                "type": "session_meta",
                "payload": {"id": "session-1234"},
            },
            {
                "timestamp": "2026-02-06T07:11:42.273Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "developer",
                    "content": [{"type": "input_text", "text": "System guidance"}],
                },
            },
            {
                "timestamp": "2026-02-06T07:11:43.000Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Find bug in indexing"}],
                },
            },
            {
                "timestamp": "2026-02-06T07:11:44.000Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "I found the issue."}],
                },
            },
            {
                "timestamp": "2026-02-06T07:11:45.000Z",
                "type": "event_msg",
                "payload": {"type": "token_count"},
            },
        ],
    )

    monkeypatch.setattr(
        PathResolver,
        "resolve_codex_dirs",
        staticmethod(lambda _cfg=None: [codex_root]),
    )

    connector = CodexConnector()
    discovered = connector.discover_files(Mock())

    assert rollout in discovered
    assert connector.can_parse(rollout)

    record = connector.parse(rollout, embedding_id=0)
    assert record.conversation_id == "session-1234"
    assert record.project_id == "codex"
    assert record.message_count == 3
    assert record.messages[0].role == "system"
    assert record.messages[1].role == "user"
    assert record.messages[2].role == "assistant"
    assert "Find bug in indexing" in record.full_text


def test_codex_parses_command_history_jsonl(tmp_path: Path) -> None:
    history = tmp_path / "history.jsonl"
    _write_jsonl(
        history,
        [
            {"session_id": "sid-1", "ts": 1_760_000_000, "text": "/init"},
            {"session_id": "sid-1", "ts": 1_760_000_100, "text": "run tests"},
        ],
    )

    connector = CodexConnector()
    assert connector.can_parse(history)

    record = connector.parse(history, embedding_id=0)
    assert record.conversation_id == "history"
    assert record.message_count == 2
    assert all(msg.role == "user" for msg in record.messages)
    assert "/init" in record.full_text
