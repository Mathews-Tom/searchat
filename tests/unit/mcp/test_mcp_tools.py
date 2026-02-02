from __future__ import annotations

import json
from pathlib import Path

import pytest

import searchat.mcp.tools as mcp_tools
from searchat.config import PathResolver


@pytest.fixture
def indexed_dataset(tmp_path: Path, temp_data_dir: Path, indexer, monkeypatch) -> Path:
    claude_root = tmp_path / "claude"
    (claude_root / "proj").mkdir(parents=True)

    conv_path = claude_root / "proj" / "conv-1.jsonl"
    conv_path.write_text(
        "\n".join(
            [
                '{"type":"user","message":{"text":"How do I implement a binary search tree in Python?"},"timestamp":"2025-01-15T10:00:00","uuid":"msg-1"}',
                '{"type":"assistant","message":{"text":"Here is code:\\n```python\\nclass Node: pass\\n```"},"timestamp":"2025-01-15T10:00:30","uuid":"msg-2"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(PathResolver, "resolve_claude_dirs", staticmethod(lambda _cfg=None: [claude_root]))
    monkeypatch.setattr(PathResolver, "resolve_vibe_dirs", staticmethod(lambda: []))
    monkeypatch.setattr(PathResolver, "resolve_opencode_dirs", staticmethod(lambda _cfg=None: []))

    indexer.index_all(force=True)

    # FAISS is mocked at import-time in tests/conftest.py and does not write to disk.
    # SearchEngine requires the file to exist before loading.
    faiss_path = temp_data_dir / "data" / "indices" / "embeddings.faiss"
    faiss_path.parent.mkdir(parents=True, exist_ok=True)
    faiss_path.write_bytes(b"")

    return temp_data_dir


def test_search_conversations_returns_results(indexed_dataset: Path) -> None:
    payload = json.loads(
        mcp_tools.search_conversations(query="binary search tree", search_dir=str(indexed_dataset))
    )

    assert payload["total"] >= 1
    assert len(payload["results"]) >= 1
    first = payload["results"][0]
    assert "conversation_id" in first
    assert "title" in first


def test_find_similar_conversations_returns_payload(indexed_dataset: Path) -> None:
    search_payload = json.loads(
        mcp_tools.search_conversations(query="binary search", search_dir=str(indexed_dataset))
    )
    conv_id = search_payload["results"][0]["conversation_id"]

    payload = json.loads(
        mcp_tools.find_similar_conversations(conversation_id=conv_id, search_dir=str(indexed_dataset), limit=3)
    )

    assert payload["conversation_id"] == conv_id
    assert "similar_conversations" in payload
    assert isinstance(payload["similar_conversations"], list)


def test_ask_about_history_includes_sources_when_enabled(indexed_dataset: Path, monkeypatch) -> None:
    def fake_completion(self, *, messages, provider, model_name=None, temperature=None, max_tokens=None):  # noqa: ANN001
        return "ok"

    monkeypatch.setattr("searchat.services.llm_service.LLMService.completion", fake_completion)

    payload = json.loads(
        mcp_tools.ask_about_history(question="What was the code?", include_sources=True, search_dir=str(indexed_dataset))
    )

    assert payload["answer"] == "ok"
    assert isinstance(payload["sources"], list)
    assert len(payload["sources"]) >= 1
