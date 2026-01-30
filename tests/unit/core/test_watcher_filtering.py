from __future__ import annotations

from queue import Queue
from pathlib import Path

from searchat.core.watcher import ConversationEventHandler


def test_watcher_filters_files_without_connector(monkeypatch, tmp_path: Path):
    q: Queue = Queue()
    handler = ConversationEventHandler(q)

    p = tmp_path / "random.json"
    p.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        "searchat.core.watcher.detect_connector",
        lambda _path: (_ for _ in ()).throw(ValueError("no connector")),
    )
    assert handler._should_process(str(p)) is False

    monkeypatch.setattr("searchat.core.watcher.detect_connector", lambda _path: object())
    assert handler._should_process(str(p)) is True
