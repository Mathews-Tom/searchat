import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from searchat.config import Config
from searchat.core.connectors import detect_connector, supported_extensions
from searchat.core.connectors.registry import (
    register_connector,
    get_connectors,
    discover_all_files,
    discover_watch_dirs,
    _CONNECTORS,
)


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


def test_detect_connector_codex_history_jsonl(tmp_path):
    file_path = tmp_path / "history.jsonl"
    file_path.write_text(
        json.dumps({"session_id": "sid-1", "ts": 1_760_000_000, "text": "hello"}) + "\n",
        encoding="utf-8",
    )
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


# ---------------------------------------------------------------------------
# Registry mutation tests (save/restore _CONNECTORS)
# ---------------------------------------------------------------------------

@dataclass
class _StubConnector:
    """Minimal connector satisfying AgentConnector protocol."""

    name: str = "stub"
    supported_extensions: tuple[str, ...] = (".stub",)

    def discover_files(self, config):
        return []

    def can_parse(self, path):
        return path.suffix == ".stub"

    def parse(self, path, embedding_id):
        raise NotImplementedError


@pytest.fixture()
def _isolated_registry():
    """Save and restore _CONNECTORS around a test."""
    original = _CONNECTORS[:]
    yield
    _CONNECTORS.clear()
    _CONNECTORS.extend(original)


class TestRegisterConnectorValidation:
    """Tests for register_connector edge cases."""

    def test_missing_attribute_raises(self, _isolated_registry):
        class Bad:
            name = "bad"
            supported_extensions = (".b",)
            def discover_files(self, config):
                return []
            def can_parse(self, path):
                return False

        with pytest.raises(ValueError, match="missing required attribute"):
            register_connector(Bad())

    def test_extensions_must_be_tuple(self, _isolated_registry):
        conn = _StubConnector()
        object.__setattr__(conn, "supported_extensions", [".stub"])
        with pytest.raises(ValueError, match="must be a tuple"):
            register_connector(conn)

    def test_invalid_extension_format(self, _isolated_registry):
        conn = _StubConnector()
        object.__setattr__(conn, "supported_extensions", ("stub",))
        with pytest.raises(ValueError, match="Invalid extension"):
            register_connector(conn)

    def test_duplicate_name_raises(self, _isolated_registry):
        register_connector(_StubConnector())
        with pytest.raises(ValueError, match="already registered"):
            register_connector(_StubConnector())


class TestDiscoverAllFiles:
    """Tests for discover_all_files."""

    def test_empty_with_no_connectors(self, _isolated_registry):
        _CONNECTORS.clear()
        config = Config.load()
        assert discover_all_files(config) == []


class TestDiscoverWatchDirs:
    """Tests for discover_watch_dirs."""

    def test_empty_with_no_connectors(self, _isolated_registry):
        _CONNECTORS.clear()
        config = Config.load()
        assert discover_watch_dirs(config) == []

    def test_uses_watch_dirs_method_if_present(self, _isolated_registry, tmp_path):
        watch_dir = tmp_path / "watch"
        watch_dir.mkdir()

        @dataclass
        class WatchConnector:
            name: str = "watcher"
            supported_extensions: tuple[str, ...] = (".w",)
            def discover_files(self, config):
                return []
            def can_parse(self, path):
                return False
            def parse(self, path, embedding_id):
                raise NotImplementedError
            def watch_dirs(self, config):
                return [watch_dir]

        _CONNECTORS.clear()
        register_connector(WatchConnector())
        config = Config.load()
        dirs = discover_watch_dirs(config)
        assert watch_dir in dirs

    def test_deduplicates_parent_dirs(self, _isolated_registry, tmp_path):
        fake_file = tmp_path / "conv.stub"
        fake_file.touch()

        @dataclass
        class DupConnector:
            name: str = "dup"
            supported_extensions: tuple[str, ...] = (".stub",)
            def discover_files(self, config):
                return [fake_file, fake_file]
            def can_parse(self, path):
                return True
            def parse(self, path, embedding_id):
                raise NotImplementedError

        _CONNECTORS.clear()
        register_connector(DupConnector())
        config = Config.load()
        dirs = discover_watch_dirs(config)
        assert len(dirs) == 1
