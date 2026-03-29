"""Unit tests for VibeConnector V2 methods."""
from __future__ import annotations

import json

import pytest

from searchat.core.connectors.vibe import VibeConnector


@pytest.fixture
def connector() -> VibeConnector:
    return VibeConnector()


@pytest.fixture
def vibe_json(tmp_path):
    """Create a minimal Vibe session JSON file."""
    data = {
        "metadata": {
            "session_id": "vibe-session-42",
            "start_time": "2026-03-29T10:00:00",
            "end_time": "2026-03-29T10:30:00",
            "environment": {
                "working_directory": "/home/user/myproject",
            },
        },
        "messages": [
            {"role": "user", "content": "Add a login page"},
            {"role": "assistant", "content": "I'll create the login component."},
            {"role": "system", "content": "ignored"},
        ],
    }
    path = tmp_path / "session.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class TestVibeLoadMessages:
    def test_load_messages_returns_user_and_assistant(self, connector: VibeConnector, vibe_json) -> None:
        messages = connector.load_messages(vibe_json)
        assert len(messages) == 2
        assert messages[0] == {"role": "user", "content": "Add a login page"}
        assert messages[1] == {"role": "assistant", "content": "I'll create the login component."}

    def test_load_messages_skips_empty_content(self, connector: VibeConnector, tmp_path) -> None:
        data = {"metadata": {}, "messages": [{"role": "user", "content": ""}]}
        path = tmp_path / "empty_msg.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        assert connector.load_messages(path) == []


class TestVibeExtractCwd:
    def test_extract_cwd(self, connector: VibeConnector, vibe_json) -> None:
        assert connector.extract_cwd(vibe_json) == "/home/user/myproject"

    def test_extract_cwd_missing_env(self, connector: VibeConnector, tmp_path) -> None:
        data = {"metadata": {}, "messages": []}
        path = tmp_path / "no_env.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        assert connector.extract_cwd(path) is None

    def test_extract_cwd_empty_string(self, connector: VibeConnector, tmp_path) -> None:
        data = {"metadata": {"environment": {"working_directory": "  "}}, "messages": []}
        path = tmp_path / "blank.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        assert connector.extract_cwd(path) is None


class TestVibeBuildResumeCommand:
    def test_build_resume_command(self, connector: VibeConnector, vibe_json) -> None:
        cmd = connector.build_resume_command(vibe_json)
        assert cmd == "vibe --session vibe-session-42"

    def test_build_resume_command_no_session_id(self, connector: VibeConnector, tmp_path) -> None:
        data = {"metadata": {}, "messages": []}
        path = tmp_path / "no_id.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        assert connector.build_resume_command(path) is None
