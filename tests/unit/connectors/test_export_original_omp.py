"""Round-trip export/re-parse tests for `OmpConnector.export_original` (M8).

Exercises `export_original` only via `services.source_lifecycle.verify_roundtrip`
against a real parsed `ConversationRecord` -- never a hand-constructed one.
The fixture covers all four raw omp roles (`user`, `assistant`, `developer`,
`toolresult`/`bashexecution`) so `_REVERSE_ROLE_MAP` is actually exercised,
including the many-to-one collapse of `toolresult`/`bashexecution` onto the
normalized `"tool"` role.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from searchat.core.connectors.omp import OmpConnector
from searchat.services.source_lifecycle import verify_roundtrip


@pytest.fixture
def connector() -> OmpConnector:
    return OmpConnector()


def _write_session(tmp_path: Path, slug: str, filename: str, lines: list[dict]) -> Path:
    slug_dir = tmp_path / slug
    slug_dir.mkdir(parents=True, exist_ok=True)
    path = slug_dir / filename
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")
    return path


def _text_message(role: str, text: str, timestamp: str) -> dict:
    return {
        "type": "message",
        "message": {"role": role, "content": [{"type": "text", "text": text}]},
        "timestamp": timestamp,
    }


class TestOmpExportOriginalRoundtrip:
    def test_roundtrip_covers_all_four_raw_roles(self, connector: OmpConnector, tmp_path: Path) -> None:
        lines = [
            {
                "type": "session",
                "id": "01900000-0000-7000-8000-0000000000ff",
                "title": "Investigate flaky test",
            },
            _text_message("user", "Why is test_foo flaky?", "2026-04-05T09:00:00"),
            _text_message(
                "assistant",
                "It relies on wall-clock time; let's mock the clock.",
                "2026-04-05T09:00:05",
            ),
            _text_message(
                "developer",
                "System policy: never delete source JSONLs without explicit --force.",
                "2026-04-05T09:00:10",
            ),
            _text_message("toolresult", "pytest tests/test_foo.py -q\n1 passed", "2026-04-05T09:00:15"),
            _text_message(
                "bashexecution",
                "$ pytest tests/test_foo.py -q -k flaky\n1 passed in 0.12s",
                "2026-04-05T09:00:20",
            ),
        ]
        filename = "2026-04-05T09-00-00-000Z_01900000-0000-7000-8000-0000000000ff.jsonl"
        path = _write_session(tmp_path, "-tmp-demo-project", filename, lines)

        record = connector.parse(path, embedding_id=7)

        assert record.conversation_id == "01900000-0000-7000-8000-0000000000ff"
        assert record.title == "Investigate flaky test"
        assert record.message_count == 5
        roles = [m.role for m in record.messages]
        assert roles == ["user", "assistant", "system", "tool", "tool"]
        assert any(m.role == "system" for m in record.messages)
        assert any(m.role == "tool" for m in record.messages)

        result = verify_roundtrip(connector, record)

        assert result.ok is True
        assert result.mismatches == ()
        assert result.reason is None

        exported = connector.export_original(record)
        assert isinstance(exported, bytes)
        assert len(exported) > 0
