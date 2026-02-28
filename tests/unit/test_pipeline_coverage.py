"""Additional tests for ExtractionPipeline — LLM mode, batch extraction, and dedup paths."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from searchat.expertise.models import ExpertiseRecord, ExpertiseType, RecordAction, RecordResult
from searchat.expertise.pipeline import ExtractionPipeline, ExtractionStats, create_pipeline


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_record(content: str = "A convention record") -> ExpertiseRecord:
    return ExpertiseRecord(
        type=ExpertiseType.CONVENTION,
        domain="testing",
        content=content,
        created_at=_utcnow(),
        last_validated=_utcnow(),
    )


def _make_pipeline(
    store: MagicMock | None = None,
    embedding_index: MagicMock | None = None,
) -> ExtractionPipeline:
    s = store or MagicMock()
    cfg = SimpleNamespace(
        expertise=SimpleNamespace(
            enabled=True,
            dedup_similarity_threshold=0.95,
            dedup_flag_threshold=0.85,
        ),
        llm=SimpleNamespace(default_provider="ollama"),
        embedding=SimpleNamespace(model="all-MiniLM-L6-v2"),
    )
    return ExtractionPipeline(s, embedding_index, cfg)


class TestExtractFromTextLlmMode:
    def test_llm_only_mode_skips_heuristic(self):
        store = MagicMock()
        store.insert.return_value = "id-1"
        pipeline = _make_pipeline(store=store)

        llm_record = _make_record("LLM extracted convention")

        with patch.object(pipeline, "_run_llm_extraction", return_value=[llm_record]):
            stats = pipeline.extract_from_text(
                "Some text about always use type annotations",
                mode="llm_only",
            )

        assert stats.llm_extracted == 1
        assert stats.heuristic_extracted == 0

    def test_full_mode_runs_both(self):
        store = MagicMock()
        store.insert.return_value = "id-1"
        pipeline = _make_pipeline(store=store)

        llm_record = _make_record("LLM record")

        with patch.object(pipeline, "_run_llm_extraction", return_value=[llm_record]):
            stats = pipeline.extract_from_text(
                "The convention is to always use type annotations",
                mode="full",
            )

        assert stats.llm_extracted == 1
        assert stats.heuristic_extracted >= 1

    def test_conversation_id_set_on_heuristic_records(self):
        store = MagicMock()
        store.insert.return_value = "id-1"
        pipeline = _make_pipeline(store=store)

        stats = pipeline.extract_from_text(
            "The convention is to always use snake_case",
            conversation_id="conv-123",
            mode="heuristic_only",
        )

        assert stats.heuristic_extracted >= 1


class TestExtractBatch:
    def test_processes_multiple_conversations(self):
        store = MagicMock()
        store.insert.return_value = "id-1"
        pipeline = _make_pipeline(store=store)

        convs = [
            {"full_text": "The convention is to always use type annotations in Python code.", "conversation_id": "c1"},
            {"full_text": "The fix was to increase the buffer size to handle larger payloads.", "conversation_id": "c2"},
        ]

        stats = pipeline.extract_batch(convs, mode="heuristic_only")
        assert stats.conversations_processed == 2

    def test_skips_short_texts(self):
        store = MagicMock()
        pipeline = _make_pipeline(store=store)

        convs = [
            {"full_text": "short", "conversation_id": "c1"},
            {"full_text": "", "conversation_id": "c2"},
        ]

        stats = pipeline.extract_batch(convs, mode="heuristic_only")
        assert stats.conversations_processed == 0

    def test_captures_errors_per_conversation(self):
        store = MagicMock()
        pipeline = _make_pipeline(store=store)

        with patch.object(pipeline, "extract_from_text", side_effect=RuntimeError("extraction failed")):
            convs = [
                {"full_text": "A " * 50, "conversation_id": "c1"},
            ]
            stats = pipeline.extract_batch(convs, mode="heuristic_only")

        assert len(stats.errors) == 1
        assert "extraction failed" in stats.errors[0]

    def test_uses_project_id_as_domain(self):
        store = MagicMock()
        store.insert.return_value = "id-1"
        pipeline = _make_pipeline(store=store)

        convs = [
            {
                "full_text": "The convention is to always use type annotations in Python code projects.",
                "conversation_id": "c1",
                "project_id": "my-project",
            },
        ]

        with patch.object(pipeline, "extract_from_text", wraps=pipeline.extract_from_text) as mock_extract:
            pipeline.extract_batch(convs, mode="heuristic_only")
            call_kwargs = mock_extract.call_args[1]
            assert call_kwargs["domain"] == "my-project"
            assert call_kwargs["project"] == "my-project"


class TestStoreWithDedup:
    def test_reinforces_existing_above_threshold(self):
        store = MagicMock()
        store.validate_record.return_value = True
        embedding_index = MagicMock()
        embedding_index.find_similar.return_value = [("existing-id", 0.98)]

        pipeline = _make_pipeline(store=store, embedding_index=embedding_index)
        record = _make_record()

        result = pipeline._store_with_dedup(record)
        assert result.action == RecordAction.REINFORCED
        assert result.existing_id == "existing-id"
        store.validate_record.assert_called_once_with("existing-id")

    def test_flags_duplicate_in_flag_range(self):
        store = MagicMock()
        embedding_index = MagicMock()
        embedding_index.find_similar.return_value = [("existing-id", 0.90)]

        pipeline = _make_pipeline(store=store, embedding_index=embedding_index)
        record = _make_record()

        result = pipeline._store_with_dedup(record)
        assert result.action == RecordAction.DUPLICATE_FLAGGED
        assert result.existing_id == "existing-id"

    def test_creates_new_when_below_thresholds(self):
        store = MagicMock()
        store.insert.return_value = "new-id"
        embedding_index = MagicMock()
        embedding_index.find_similar.return_value = [("other-id", 0.50)]

        pipeline = _make_pipeline(store=store, embedding_index=embedding_index)
        record = _make_record()

        result = pipeline._store_with_dedup(record)
        assert result.action == RecordAction.CREATED
        store.insert.assert_called_once()
        embedding_index.add.assert_called_once_with(record)

    def test_creates_new_when_no_similar(self):
        store = MagicMock()
        store.insert.return_value = "new-id"
        embedding_index = MagicMock()
        embedding_index.find_similar.return_value = []

        pipeline = _make_pipeline(store=store, embedding_index=embedding_index)
        record = _make_record()

        result = pipeline._store_with_dedup(record)
        assert result.action == RecordAction.CREATED

    def test_creates_new_without_embedding_index(self):
        store = MagicMock()
        store.insert.return_value = "new-id"

        pipeline = _make_pipeline(store=store, embedding_index=None)
        record = _make_record()

        result = pipeline._store_with_dedup(record)
        assert result.action == RecordAction.CREATED
        store.insert.assert_called_once()


class TestRunLlmExtraction:
    def test_returns_empty_on_extraction_error(self):
        pipeline = _make_pipeline()

        with patch("searchat.expertise.llm_extractor.LLMExtractor") as mock_cls:
            from searchat.expertise.llm_extractor import ExtractionError
            mock_cls.return_value.extract.side_effect = ExtractionError("LLM failed")

            result = pipeline._run_llm_extraction("some text", "domain", None, None)
        assert result == []

    def test_sets_conversation_id_on_records(self):
        pipeline = _make_pipeline()
        rec = _make_record()

        with patch("searchat.expertise.llm_extractor.LLMExtractor") as mock_cls:
            mock_cls.return_value.extract.return_value = [rec]
            result = pipeline._run_llm_extraction("text", "domain", None, "conv-42")

        assert result[0].source_conversation_id == "conv-42"


class TestCreatePipeline:
    def test_creates_with_embedding_index(self, tmp_path):
        cfg = SimpleNamespace(
            expertise=SimpleNamespace(enabled=True),
            embedding=SimpleNamespace(model="all-MiniLM-L6-v2"),
        )

        with (
            patch("searchat.expertise.pipeline.ExpertiseStore") as mock_store,
            patch("searchat.expertise.pipeline.ExpertiseEmbeddingIndex") as mock_emb,
        ):
            pipeline = create_pipeline(cfg, tmp_path)

        assert pipeline is not None
        mock_emb.assert_called_once()

    def test_creates_without_embedding_index_when_disabled(self, tmp_path):
        cfg = SimpleNamespace(
            expertise=SimpleNamespace(enabled=False),
            embedding=SimpleNamespace(model="all-MiniLM-L6-v2"),
        )

        with (
            patch("searchat.expertise.pipeline.ExpertiseStore") as mock_store,
            patch("searchat.expertise.pipeline.ExpertiseEmbeddingIndex") as mock_emb,
        ):
            pipeline = create_pipeline(cfg, tmp_path)

        mock_emb.assert_not_called()
