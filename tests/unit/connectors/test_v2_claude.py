"""Unit tests for ClaudeConnector V2 methods."""
from __future__ import annotations

import json

import pytest

from searchat.core.connectors.claude import ClaudeConnector


@pytest.fixture
def connector() -> ClaudeConnector:
    return ClaudeConnector()


@pytest.fixture
def claude_jsonl(tmp_path):
    """Create a minimal Claude JSONL conversation file."""
    lines = [
        {"type": "user", "timestamp": "2026-03-29T10:00:00", "message": {"content": "Fix the bug in auth.py"}},
        {"type": "assistant", "timestamp": "2026-03-29T10:00:05", "message": {"content": "I'll fix the bug now."}},
        {
            "type": "assistant",
            "timestamp": "2026-03-29T10:00:10",
            "message": {
                "content": [
                    {"type": "text", "text": "Done."},
                    {
                        "type": "tool_use",
                        "name": "Edit",
                        "input": {"file_path": "/home/user/project/src/auth.py"},
                    },
                    {
                        "type": "tool_use",
                        "name": "Read",
                        "input": {"file_path": "/home/user/project/src/models.py"},
                    },
                ],
            },
        },
    ]
    path = tmp_path / "abc123.jsonl"
    path.write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")
    return path


class TestClaudeLoadMessages:
    def test_load_messages_returns_user_and_assistant(self, connector: ClaudeConnector, claude_jsonl) -> None:
        messages = connector.load_messages(claude_jsonl)
        assert len(messages) >= 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Fix the bug in auth.py"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == "I'll fix the bug now."

    def test_load_messages_empty_file(self, connector: ClaudeConnector, tmp_path) -> None:
        path = tmp_path / "empty.jsonl"
        path.write_text("", encoding="utf-8")
        assert connector.load_messages(path) == []

    def test_load_messages_skips_non_user_assistant(self, connector: ClaudeConnector, tmp_path) -> None:
        lines = [
            {"type": "system", "message": {"content": "system msg"}},
            {"type": "user", "message": {"content": "hello"}},
        ]
        path = tmp_path / "mixed.jsonl"
        path.write_text("\n".join(json.dumps(l) for l in lines), encoding="utf-8")
        messages = connector.load_messages(path)
        assert len(messages) == 1
        assert messages[0]["role"] == "user"


class TestClaudeExtractCwd:
    def test_extract_cwd_from_tool_use_paths(self, connector: ClaudeConnector, claude_jsonl) -> None:
        cwd = connector.extract_cwd(claude_jsonl)
        assert cwd is not None
        assert "project" in cwd

    def test_extract_cwd_no_tool_use(self, connector: ClaudeConnector, tmp_path) -> None:
        lines = [
            {"type": "user", "message": {"content": "hello"}},
            {"type": "assistant", "message": {"content": "hi"}},
        ]
        path = tmp_path / "no_tools.jsonl"
        path.write_text("\n".join(json.dumps(l) for l in lines), encoding="utf-8")
        assert connector.extract_cwd(path) is None

    def test_extract_cwd_relative_paths_only(self, connector: ClaudeConnector, tmp_path) -> None:
        lines = [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "tool_use", "name": "Read", "input": {"file_path": "relative/path.py"}},
                    ],
                },
            },
        ]
        path = tmp_path / "relative.jsonl"
        path.write_text("\n".join(json.dumps(l) for l in lines), encoding="utf-8")
        assert connector.extract_cwd(path) is None


class TestClaudeBuildResumeCommand:
    def test_build_resume_command(self, connector: ClaudeConnector, claude_jsonl) -> None:
        cmd = connector.build_resume_command(claude_jsonl)
        assert cmd == "claude --conversation abc123"

    def test_build_resume_command_uses_stem(self, connector: ClaudeConnector, tmp_path) -> None:
        path = tmp_path / "my-session-id.jsonl"
        path.write_text("{}\n", encoding="utf-8")
        cmd = connector.build_resume_command(path)
        assert cmd == "claude --conversation my-session-id"
