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


def test_supported_extensions():
    extensions = supported_extensions()
    assert ".jsonl" in extensions
    assert ".json" in extensions
