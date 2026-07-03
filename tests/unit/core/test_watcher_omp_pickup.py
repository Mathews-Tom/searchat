"""Incremental watcher picks up a newly created omp session file."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from searchat.config import Config
from searchat.config.path_resolver import PathResolver
from searchat.core.watcher import ConversationWatcher


@pytest.fixture
def omp_sessions_root(tmp_path: Path) -> Path:
    root = tmp_path / "omp-sessions"
    (root / "-tmp-demo-project").mkdir(parents=True)
    return root


def test_watcher_picks_up_new_omp_session_file(monkeypatch, omp_sessions_root: Path) -> None:
    monkeypatch.setattr(PathResolver, "resolve_omp_dirs", staticmethod(lambda _cfg=None: [omp_sessions_root]))
    monkeypatch.setattr(PathResolver, "resolve_claude_dirs", staticmethod(lambda _cfg=None: []))
    monkeypatch.setattr(PathResolver, "resolve_vibe_dirs", staticmethod(lambda: []))
    monkeypatch.setattr(PathResolver, "resolve_opencode_dirs", staticmethod(lambda _cfg=None: []))

    config = Config.load()
    updates: list[list[str]] = []
    watcher = ConversationWatcher(
        config,
        on_update=updates.append,
        batch_delay_seconds=0.2,
        debounce_seconds=0.05,
    )
    assert omp_sessions_root in watcher.watched_dirs

    watcher.start()
    try:
        new_session = omp_sessions_root / "-tmp-demo-project" / (
            "2026-04-01T00-00-00-000Z_01900000-0000-7000-8000-0000000000ff.jsonl"
        )
        new_session.write_text(
            '{"type":"session","id":"s1","cwd":"/tmp/demo-project","title":"t"}\n'
            '{"type":"message","id":"m1","message":{"role":"user",'
            '"content":[{"type":"text","text":"hello"}]}}\n',
            encoding="utf-8",
        )

        deadline = time.time() + 5.0
        while time.time() < deadline and not updates:
            time.sleep(0.1)
    finally:
        watcher.stop()

    assert updates, "watcher never reported the new omp session file"
    picked_up = [p for batch in updates for p in batch]
    assert str(new_session) in picked_up
