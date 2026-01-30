from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

from searchat.core.connectors import discover_watch_dirs
from searchat.config.path_resolver import PathResolver


def test_discover_watch_dirs_uses_connector_watch_dirs(monkeypatch, tmp_path: Path):
    claude_root = tmp_path / "claude"
    claude_root.mkdir()
    vibe_root = tmp_path / "vibe"
    vibe_root.mkdir()
    opencode_root = tmp_path / "opencode"
    (opencode_root / "storage").mkdir(parents=True)

    monkeypatch.setattr(PathResolver, "resolve_claude_dirs", staticmethod(lambda _cfg=None: [claude_root]))
    monkeypatch.setattr(PathResolver, "resolve_vibe_dirs", staticmethod(lambda: [vibe_root]))
    monkeypatch.setattr(PathResolver, "resolve_opencode_dirs", staticmethod(lambda _cfg=None: [opencode_root]))

    config = Mock()
    watch_dirs = discover_watch_dirs(config)

    assert claude_root in watch_dirs
    assert vibe_root in watch_dirs
    assert (opencode_root / "storage") in watch_dirs

    # Ensure we are not generating a directory per discovered file.
    assert len(watch_dirs) == 3
