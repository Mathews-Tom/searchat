"""Round-trip export/re-parse tests for `GeminiCLIConnector.export_original` (M8).

Exercises `export_original` only via `services.source_lifecycle.verify_roundtrip`
against a real parsed `ConversationRecord` -- never a hand-constructed one.
The fixture is placed at `<tmp>/<project_hash>/chats/<id>.json`, matching
`_project_hash_from_path`'s expectation, so `record.project_id` is a real
`gemini-<hash>` value rather than the bare `gemini` fallback -- proving the
path-derived-identity round trip (which `verify_roundtrip` covers by
mirroring the full directory structure) is actually exercised.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from searchat.core.connectors.gemini import GeminiCLIConnector
from searchat.services.source_lifecycle import verify_roundtrip


@pytest.fixture
def connector() -> GeminiCLIConnector:
    return GeminiCLIConnector()


def _write_chat(tmp_path: Path, project_hash: str, chat_id: str, history: list[dict]) -> Path:
    chats_dir = tmp_path / project_hash / "chats"
    chats_dir.mkdir(parents=True, exist_ok=True)
    path = chats_dir / f"{chat_id}.json"
    path.write_text(json.dumps({"history": history}), encoding="utf-8")
    return path


class TestGeminiExportOriginalRoundtrip:
    def test_roundtrip_preserves_project_hash_and_messages(
        self, connector: GeminiCLIConnector, tmp_path: Path
    ) -> None:
        # "model" is Gemini's native role spelling but GeminiCLIConnector.parse
        # lowercases and only accepts user/assistant/system/tool -- "model"
        # would be silently dropped, so "assistant" is used here instead.
        history = [
            {
                "role": "user",
                "content": "Summarize this repository's architecture.",
                "timestamp": "2026-02-01T09:00:00",
            },
            {
                "role": "assistant",
                "content": "The repository uses a hybrid BM25 + FAISS search engine.",
                "timestamp": "2026-02-01T09:01:00",
            },
        ]
        path = _write_chat(tmp_path, "8f3c1a9b2d4e5f60", "chat-session-001", history)

        record = connector.parse(path, embedding_id=5)

        assert record.project_id.startswith("gemini-")
        assert record.project_id == "gemini-8f3c1a9b2d4e5f60"
        assert record.message_count == 2
        assert [m.role for m in record.messages] == ["user", "assistant"]

        result = verify_roundtrip(connector, record)

        assert result.ok is True
        assert result.mismatches == ()
        assert result.reason is None

        exported = connector.export_original(record)
        assert isinstance(exported, bytes)
        assert len(exported) > 0
