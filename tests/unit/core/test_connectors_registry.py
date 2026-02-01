import json
from pathlib import Path

from searchat.core.connectors import detect_connector, supported_extensions


def test_detect_connector_claude(tmp_path):
    file_path = tmp_path / "conv.jsonl"
    file_path.write_text("{}\n", encoding="utf-8")
    connector = detect_connector(file_path)
    assert connector.name == "claude"


def test_detect_connector_vibe(tmp_path):
    file_path = tmp_path / "session.json"
    file_path.write_text(json.dumps({"metadata": {}, "messages": []}), encoding="utf-8")
    connector = detect_connector(file_path)
    assert connector.name == "vibe"


def test_detect_connector_opencode(tmp_path):
    file_path = tmp_path / "session.json"
    file_path.write_text(json.dumps({"projectID": "proj", "sessionID": "sess"}), encoding="utf-8")
    connector = detect_connector(file_path)
    assert connector.name == "opencode"


def test_detect_connector_codex(tmp_path):
    file_path = tmp_path / "rollout-0001.jsonl"
    file_path.write_text(json.dumps({"role": "user", "content": "Hello"}) + "\n", encoding="utf-8")
    connector = detect_connector(file_path)
    assert connector.name == "codex"


def test_detect_connector_gemini(tmp_path):
    file_path = tmp_path / "chat.json"
    file_path.write_text(json.dumps({"history": [{"role": "user", "content": "Hi"}]}), encoding="utf-8")
    connector = detect_connector(file_path)
    assert connector.name == "gemini"


def test_detect_connector_continue(tmp_path):
    file_path = tmp_path / "session.json"
    file_path.write_text(
        json.dumps({"workspaceDirectory": "/repo", "messages": [{"role": "user", "content": "Hi"}]}),
        encoding="utf-8",
    )
    connector = detect_connector(file_path)
    assert connector.name == "continue"


def test_detect_connector_cursor_pseudo_path():
    pseudo = Path("/tmp/state.vscdb.cursor/00000000-0000-0000-0000-000000000000.json")
    connector = detect_connector(pseudo)
    assert connector.name == "cursor"


def test_detect_connector_aider(tmp_path):
    file_path = tmp_path / ".aider.chat.history.md"
    file_path.write_text("#### user:\nHello\n", encoding="utf-8")
    connector = detect_connector(file_path)
    assert connector.name == "aider"


def test_supported_extensions():
    extensions = supported_extensions()
    assert ".jsonl" in extensions
    assert ".json" in extensions
