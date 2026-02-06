from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import Mock

from searchat.config.path_resolver import PathResolver
from searchat.core.connectors.aider import AiderConnector
from searchat.core.connectors.claude import ClaudeConnector
from searchat.core.connectors.codex import CodexConnector
from searchat.core.connectors.continue_cli import ContinueConnector
from searchat.core.connectors.cursor import CursorConnector
from searchat.core.connectors.gemini import GeminiCLIConnector
from searchat.core.connectors.opencode import OpenCodeConnector
from searchat.core.connectors.vibe import VibeConnector


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _assert_non_empty_record(record) -> None:
    assert record.message_count > 0
    assert record.messages
    assert record.full_text.strip()


def test_claude_connector_contract(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "claude-projects"
    conv = root / "proj-a" / "conv.jsonl"
    _write_jsonl(
        conv,
        [
            {"type": "user", "timestamp": "2026-02-06T12:00:00", "message": {"content": "hello"}},
            {"type": "assistant", "timestamp": "2026-02-06T12:00:01", "message": {"content": "hi"}},
        ],
    )
    monkeypatch.setattr(PathResolver, "resolve_claude_dirs", staticmethod(lambda _cfg=None: [root]))

    connector = ClaudeConnector()
    discovered = connector.discover_files(Mock())
    assert conv in discovered
    assert connector.can_parse(conv)
    _assert_non_empty_record(connector.parse(conv, embedding_id=0))


def test_vibe_connector_contract(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "vibe" / "logs" / "session"
    session = root / "session.json"
    _write_json(
        session,
        {
            "metadata": {
                "session_id": "vibe-1",
                "start_time": "2026-02-06T12:00:00",
                "end_time": "2026-02-06T12:01:00",
                "environment": {"working_directory": "/tmp/repo"},
            },
            "messages": [
                {"role": "user", "content": "question"},
                {"role": "assistant", "content": "answer"},
            ],
        },
    )
    monkeypatch.setattr(PathResolver, "resolve_vibe_dirs", staticmethod(lambda: [root]))

    connector = VibeConnector()
    discovered = connector.discover_files(Mock())
    assert session in discovered
    assert connector.can_parse(session)
    _assert_non_empty_record(connector.parse(session, embedding_id=0))


def test_opencode_connector_contract(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "opencode"
    session = root / "storage" / "session" / "proj-a" / "s1.json"
    _write_json(
        session,
        {
            "projectID": "proj-a",
            "sessionID": "s1",
            "messages": [
                {"role": "user", "content": "question"},
                {"role": "assistant", "content": "answer"},
            ],
            "time": {"created": 1_760_000_000_000, "updated": 1_760_000_100_000},
        },
    )
    monkeypatch.setattr(PathResolver, "resolve_opencode_dirs", staticmethod(lambda _cfg=None: [root]))

    connector = OpenCodeConnector()
    discovered = connector.discover_files(Mock())
    assert session in discovered
    assert connector.can_parse(session)
    _assert_non_empty_record(connector.parse(session, embedding_id=0))


def test_codex_connector_contract(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / ".codex"
    rollout = root / "sessions" / "2026" / "02" / "06" / "rollout-abc.jsonl"
    _write_jsonl(
        rollout,
        [
            {"type": "session_meta", "payload": {"id": "session-abc"}, "timestamp": "2026-02-06T12:00:00Z"},
            {
                "type": "response_item",
                "timestamp": "2026-02-06T12:00:01Z",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "debug this"}],
                },
            },
            {
                "type": "response_item",
                "timestamp": "2026-02-06T12:00:02Z",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "done"}],
                },
            },
        ],
    )
    monkeypatch.setattr(PathResolver, "resolve_codex_dirs", staticmethod(lambda _cfg=None: [root]))

    connector = CodexConnector()
    discovered = connector.discover_files(Mock())
    assert rollout in discovered
    assert connector.can_parse(rollout)
    _assert_non_empty_record(connector.parse(rollout, embedding_id=0))


def test_gemini_connector_contract(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / ".gemini" / "tmp"
    chat = root / "projecthash" / "chats" / "chat-1.json"
    _write_json(
        chat,
        {
            "history": [
                {"role": "user", "content": "question"},
                {"role": "assistant", "content": "answer"},
            ]
        },
    )
    monkeypatch.setattr(PathResolver, "resolve_gemini_dirs", staticmethod(lambda _cfg=None: [root]))

    connector = GeminiCLIConnector()
    discovered = connector.discover_files(Mock())
    assert chat in discovered
    assert connector.can_parse(chat)
    _assert_non_empty_record(connector.parse(chat, embedding_id=0))


def test_continue_connector_contract(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / ".continue" / "sessions"
    session = root / "session-1.json"
    _write_json(
        session,
        {
            "workspaceDirectory": "/tmp/repo",
            "messages": [
                {"role": "user", "content": "question"},
                {"role": "assistant", "content": "answer"},
            ],
        },
    )
    _write_json(root / "sessions.json", {"items": []})
    monkeypatch.setattr(PathResolver, "resolve_continue_dirs", staticmethod(lambda _cfg=None: [root]))

    connector = ContinueConnector()
    discovered = connector.discover_files(Mock())
    assert session in discovered
    assert connector.can_parse(session)
    _assert_non_empty_record(connector.parse(session, embedding_id=0))


def test_cursor_connector_contract(monkeypatch, tmp_path: Path) -> None:
    user_root = tmp_path / "Cursor" / "User"
    db_path = user_root / "globalStorage" / "state.vscdb"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(db_path)
    try:
        con.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
        composer_id = "composer-1"
        bubble_1 = "bubble-1"
        bubble_2 = "bubble-2"

        composer = {
            "_v": 3,
            "composerId": composer_id,
            "createdAt": 1_700_000_000_000,
            "lastUpdatedAt": 1_700_000_010_000,
            "fullConversationHeadersOnly": [
                {"bubbleId": bubble_1, "type": 1},
                {"bubbleId": bubble_2, "type": 2},
            ],
        }
        bubble_one = {"_v": 2, "bubbleId": bubble_1, "type": 1, "rawText": "Hello user"}
        bubble_two = {"_v": 2, "bubbleId": bubble_2, "type": 2, "rawText": "Hello assistant"}

        con.execute("INSERT INTO ItemTable(key, value) VALUES(?, ?)", (f"composerData:{composer_id}", json.dumps(composer)))
        con.execute("INSERT INTO ItemTable(key, value) VALUES(?, ?)", (f"bubble:{bubble_1}", json.dumps(bubble_one)))
        con.execute("INSERT INTO ItemTable(key, value) VALUES(?, ?)", (f"bubble:{bubble_2}", json.dumps(bubble_two)))
        con.commit()
    finally:
        con.close()

    monkeypatch.setattr(PathResolver, "resolve_cursor_dirs", staticmethod(lambda _cfg=None: [user_root]))

    connector = CursorConnector()
    discovered = connector.discover_files(Mock())
    assert discovered
    pseudo = discovered[0]
    assert connector.can_parse(pseudo)
    _assert_non_empty_record(connector.parse(pseudo, embedding_id=0))


def test_aider_connector_contract(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "repo"
    history = root / ".aider.chat.history.md"
    history.parent.mkdir(parents=True, exist_ok=True)
    history.write_text("#### user:\nhello\n\n#### assistant:\nhi\n", encoding="utf-8")

    monkeypatch.setattr(PathResolver, "resolve_aider_dirs", staticmethod(lambda _cfg=None: [root]))

    connector = AiderConnector()
    discovered = connector.discover_files(Mock())
    assert history in discovered
    assert connector.can_parse(history)
    _assert_non_empty_record(connector.parse(history, embedding_id=0))
