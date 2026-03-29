"""Tests for Distiller exchange segmentation and file path extraction."""
from __future__ import annotations

import pytest

from searchat.palace.distiller import extract_file_paths, make_room_id, Distiller
from searchat.config import Config


@pytest.fixture
def config():
    return Config.load()


class TestExtractFilePaths:
    def test_basic_path(self):
        paths = extract_file_paths("Modified src/main.py")
        assert "src/main.py" in paths

    def test_backtick_path(self):
        paths = extract_file_paths("Look at `src/config.toml` for settings")
        assert "src/config.toml" in paths

    def test_multiple_paths_dedup(self):
        text = "Changed src/main.py and tests/test_main.py and also src/main.py"
        paths = extract_file_paths(text)
        assert paths.count("src/main.py") == 1
        assert "tests/test_main.py" in paths

    def test_windows_path_normalized(self):
        paths = extract_file_paths("File at src\\api\\app.py")
        assert "src/api/app.py" in paths

    def test_dotslash_stripped(self):
        paths = extract_file_paths("Run ./config.toml")
        assert "config.toml" in paths

    def test_no_paths(self):
        paths = extract_file_paths("No file paths here")
        assert paths == []

    def test_various_extensions(self):
        text = "Files: app.ts, style.css, data.json, Dockerfile"
        paths = extract_file_paths(text)
        assert "app.ts" in paths
        assert "style.css" in paths
        assert "data.json" in paths

    def test_deep_path(self):
        paths = extract_file_paths("Look at src/searchat/palace/storage.py")
        assert "src/searchat/palace/storage.py" in paths


class TestMakeRoomId:
    def test_deterministic(self):
        id1 = make_room_id("file", "auth", "proj-1")
        id2 = make_room_id("file", "auth", "proj-1")
        assert id1 == id2

    def test_different_inputs_different_ids(self):
        id1 = make_room_id("file", "auth", "proj-1")
        id2 = make_room_id("concept", "auth", "proj-1")
        assert id1 != id2

    def test_none_project(self):
        id1 = make_room_id("file", "auth", None)
        assert len(id1) == 16


class TestSegmentExchanges:
    def test_single_exchange(self, config, tmp_path):
        distiller = Distiller(
            search_dir=tmp_path,
            config=config,
            embedder=None,  # type: ignore[arg-type]
        )
        # Override embedder requirement since we only test segmentation
        messages = [
            {"sequence": 0, "role": "user", "content": "Hello world" * 20},
            {"sequence": 1, "role": "assistant", "content": "Hi there" * 20},
        ]
        exchanges = distiller._segment_exchanges(messages)
        assert len(exchanges) == 1
        assert exchanges[0] == (0, 1)

    def test_multiple_exchanges(self, config, tmp_path):
        distiller = Distiller(
            search_dir=tmp_path,
            config=config,
            embedder=None,  # type: ignore[arg-type]
        )
        messages = [
            {"sequence": 0, "role": "user", "content": "Hello" * 20},
            {"sequence": 1, "role": "assistant", "content": "Hi" * 20},
            {"sequence": 2, "role": "user", "content": "More" * 20},
            {"sequence": 3, "role": "assistant", "content": "Sure" * 20},
        ]
        exchanges = distiller._segment_exchanges(messages)
        assert len(exchanges) == 2

    def test_empty_messages(self, config, tmp_path):
        distiller = Distiller(
            search_dir=tmp_path,
            config=config,
            embedder=None,  # type: ignore[arg-type]
        )
        exchanges = distiller._segment_exchanges([])
        assert exchanges == []

    def test_drops_short_exchanges(self, config, tmp_path):
        distiller = Distiller(
            search_dir=tmp_path,
            config=config,
            embedder=None,  # type: ignore[arg-type]
        )
        messages = [
            {"sequence": 0, "role": "user", "content": "Hi"},
            {"sequence": 1, "role": "assistant", "content": "Hello"},
        ]
        # Min exchange chars is 50, "Hi" + "Hello" = 7 chars
        exchanges = distiller._segment_exchanges(messages)
        assert len(exchanges) == 0

    def test_splits_long_exchanges(self, config, tmp_path):
        distiller = Distiller(
            search_dir=tmp_path,
            config=config,
            embedder=None,  # type: ignore[arg-type]
        )
        # Create an exchange with > max_ply_length (20) messages
        messages = [
            {"sequence": i, "role": "user" if i % 2 == 0 else "assistant", "content": "Word " * 30}
            for i in range(30)
        ]
        exchanges = distiller._segment_exchanges(messages)
        # Should be split into chunks of max_ply_length
        assert all(end - start + 1 <= config.distillation.max_ply_length for start, end in exchanges)
