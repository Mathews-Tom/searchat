"""Unit tests for `ContinueConnector.export_original` / round-trip verification (M8).

Continue's `project_id` is either the constant `"continue"` (no workspace
recorded) or a one-way `continue-<sha1(workspaceDirectory)[:10]>` hash
computed at parse time. The hash cannot be inverted back to the original
`workspaceDirectory` from a `ConversationRecord` alone, so
`ContinueConnector.export_original` deliberately omits `workspaceDirectory`
from its re-serialized JSON in both cases (see its docstring). These tests
prove both halves of that contract: the fully-reconstructible case round
trips exactly, and the hash-derived case is honestly reported as a
`project_id` mismatch rather than silently mis-reported as reversible.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from searchat.core.connectors.continue_cli import ContinueConnector
from searchat.services.source_lifecycle import verify_roundtrip

_HISTORY = [
    {
        "role": "user",
        "content": "How do I implement a binary search in Python?",
        "timestamp": "2024-01-15T10:00:00",
    },
    {
        "role": "assistant",
        "content": (
            "Here's a binary search implementation:\n\n"
            "```python\ndef binary_search(arr, target):\n    pass\n```"
        ),
        "timestamp": "2024-01-15T10:01:00",
    },
]


@pytest.fixture
def connector() -> ContinueConnector:
    return ContinueConnector()


def _write_session(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "session.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class TestContinueRoundtripNoWorkspace:
    """No `workspaceDirectory` key in the source session -> `project_id`
    is the constant `"continue"`, which IS fully reconstructible: the
    round trip must succeed exactly, with no mismatches at all."""

    def test_roundtrip_ok_with_no_mismatches(self, connector: ContinueConnector, tmp_path: Path) -> None:
        path = _write_session(tmp_path, {"history": _HISTORY})
        record = connector.parse(path, embedding_id=1)

        assert record.project_id == "continue"

        result = verify_roundtrip(connector, record)

        assert result.ok is True
        assert result.mismatches == ()


class TestContinueRoundtripWithWorkspaceHash:
    """A `workspaceDirectory` value present at parse time -> `project_id`
    becomes the one-way hash `continue-<sha1[:10]>`. `export_original`
    cannot invert that hash back to the original workspace path (its
    docstring explains why), so `workspaceDirectory` is correctly omitted
    from the re-serialized JSON and re-parsing necessarily recomputes
    `project_id="continue"` -- a genuine, honestly-detected mismatch
    against the stored `"continue-<hash>"`, not a silent false success.
    Every other field (messages, title, timestamps, ...) must still match
    exactly, proving `project_id` is the ONLY casualty of this limitation.
    """

    def test_roundtrip_reports_project_id_as_the_only_mismatch(
        self, connector: ContinueConnector, tmp_path: Path
    ) -> None:
        payload = {"history": _HISTORY, "workspaceDirectory": "/Users/dev/my-project"}
        path = _write_session(tmp_path, payload)
        record = connector.parse(path, embedding_id=2)

        assert re.fullmatch(r"continue-[0-9a-f]{10}", record.project_id)

        result = verify_roundtrip(connector, record)

        assert result.ok is False
        assert result.mismatches == ("project_id",)
