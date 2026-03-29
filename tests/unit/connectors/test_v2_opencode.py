"""Unit tests for OpenCodeConnector V2 methods."""
from __future__ import annotations

import json

import pytest

from searchat.core.connectors.opencode import OpenCodeConnector


@pytest.fixture
def connector() -> OpenCodeConnector:
    return OpenCodeConnector()


@pytest.fixture
def opencode_session(tmp_path):
    """Create a minimal OpenCode session structure."""
    # Create directory structure: storage/session/<project>/<session>.json
    project_dir = tmp_path / "storage" / "session" / "proj-hash"
    project_dir.mkdir(parents=True)

    session_data = {
        "id": "session-abc",
        "sessionID": "session-abc",
        "projectID": "myproject",
        "title": "Test Session",
        "time": {"created": 1711699200000, "updated": 1711699800000},
    }
    session_path = project_dir / "session-abc.json"
    session_path.write_text(json.dumps(session_data), encoding="utf-8")

    # Create message files
    msg_dir = tmp_path / "storage" / "message" / "session-abc"
    msg_dir.mkdir(parents=True)
    msg1 = {"role": "user", "content": "What is this?", "time": {"created": 1711699200000}}
    msg2 = {"role": "assistant", "content": "It's a test.", "time": {"created": 1711699210000}}
    (msg_dir / "msg1.json").write_text(json.dumps(msg1), encoding="utf-8")
    (msg_dir / "msg2.json").write_text(json.dumps(msg2), encoding="utf-8")

    return session_path


class TestOpenCodeLoadMessages:
    def test_load_messages_from_message_dir(self, connector: OpenCodeConnector, opencode_session) -> None:
        messages = connector.load_messages(opencode_session)
        assert len(messages) == 2
        roles = {m["role"] for m in messages}
        assert roles == {"user", "assistant"}

    def test_load_messages_empty_session(self, connector: OpenCodeConnector, tmp_path) -> None:
        project_dir = tmp_path / "storage" / "session" / "proj"
        project_dir.mkdir(parents=True)
        data = {"id": "empty-sess", "projectID": "p"}
        path = project_dir / "empty-sess.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        assert connector.load_messages(path) == []


class TestOpenCodeExtractCwd:
    def test_extract_cwd_returns_none(self, connector: OpenCodeConnector, opencode_session) -> None:
        # OpenCode hashes project paths, raw cwd not recoverable
        assert connector.extract_cwd(opencode_session) is None


class TestOpenCodeBuildResumeCommand:
    def test_build_resume_command(self, connector: OpenCodeConnector, opencode_session) -> None:
        cmd = connector.build_resume_command(opencode_session)
        assert cmd == "opencode --session session-abc"

    def test_build_resume_command_no_id(self, connector: OpenCodeConnector, tmp_path) -> None:
        data = {"projectID": "p"}
        path = tmp_path / "no_id.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        assert connector.build_resume_command(path) is None
