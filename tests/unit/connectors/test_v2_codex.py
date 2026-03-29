"""Unit tests for CodexConnector V2 methods."""
from __future__ import annotations

import json

import pytest

from searchat.core.connectors.codex import CodexConnector


@pytest.fixture
def connector() -> CodexConnector:
    return CodexConnector()


@pytest.fixture
def codex_jsonl(tmp_path):
    """Create a minimal Codex rollout JSONL file."""
    lines = [
        {"type": "session_meta", "payload": {"id": "sess-001", "cwd": "/home/user/repo"}},
        {"role": "user", "content": "Refactor the parser", "timestamp": "2026-03-29T10:00:00"},
        {"role": "assistant", "content": "Starting refactor.", "timestamp": "2026-03-29T10:00:05"},
    ]
    path = tmp_path / "rollout-abc.jsonl"
    path.write_text("\n".join(json.dumps(l) for l in lines), encoding="utf-8")
    return path


class TestCodexLoadMessages:
    def test_load_messages_returns_messages(self, connector: CodexConnector, codex_jsonl) -> None:
        messages = connector.load_messages(codex_jsonl)
        assert len(messages) == 2
        assert messages[0] == {"role": "user", "content": "Refactor the parser"}
        assert messages[1] == {"role": "assistant", "content": "Starting refactor."}

    def test_load_messages_empty_file(self, connector: CodexConnector, tmp_path) -> None:
        path = tmp_path / "empty.jsonl"
        path.write_text("", encoding="utf-8")
        assert connector.load_messages(path) == []

    def test_load_messages_skips_session_meta(self, connector: CodexConnector, tmp_path) -> None:
        lines = [
            {"type": "session_meta", "payload": {"id": "s1"}},
        ]
        path = tmp_path / "meta_only.jsonl"
        path.write_text("\n".join(json.dumps(l) for l in lines), encoding="utf-8")
        assert connector.load_messages(path) == []


class TestCodexExtractCwd:
    def test_extract_cwd(self, connector: CodexConnector, codex_jsonl) -> None:
        assert connector.extract_cwd(codex_jsonl) == "/home/user/repo"

    def test_extract_cwd_no_meta(self, connector: CodexConnector, tmp_path) -> None:
        lines = [{"role": "user", "content": "hello"}]
        path = tmp_path / "no_meta.jsonl"
        path.write_text("\n".join(json.dumps(l) for l in lines), encoding="utf-8")
        assert connector.extract_cwd(path) is None

    def test_extract_cwd_working_directory_key(self, connector: CodexConnector, tmp_path) -> None:
        lines = [
            {"type": "session_meta", "payload": {"id": "s1", "working_directory": "/opt/project"}},
        ]
        path = tmp_path / "alt_key.jsonl"
        path.write_text("\n".join(json.dumps(l) for l in lines), encoding="utf-8")
        assert connector.extract_cwd(path) == "/opt/project"


class TestCodexBuildResumeCommand:
    def test_build_resume_command(self, connector: CodexConnector, codex_jsonl) -> None:
        cmd = connector.build_resume_command(codex_jsonl)
        assert cmd == "codex --session sess-001"

    def test_build_resume_command_no_session(self, connector: CodexConnector, tmp_path) -> None:
        lines = [{"role": "user", "content": "hello"}]
        path = tmp_path / "no_session.jsonl"
        path.write_text("\n".join(json.dumps(l) for l in lines), encoding="utf-8")
        assert connector.build_resume_command(path) is None
