"""Tests for ExtractionPipeline orchestration and dedup logic."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from searchat.expertise.models import (
    ExpertiseRecord,
    ExpertiseType,
    RecordAction,
    RecordResult,
)
from searchat.expertise.pipeline import ExtractionPipeline, ExtractionStats, create_pipeline


def _make_config(
    *,
    dedup_threshold: float = 0.95,
    flag_threshold: float = 0.80,
    expertise_enabled: bool = True,
    embedding_model: str = "all-MiniLM-L6-v2",
) -> MagicMock:
    config = MagicMock()
    config.expertise.enabled = expertise_enabled
    config.expertise.dedup_similarity_threshold = dedup_threshold
    config.expertise.dedup_flag_threshold = flag_threshold
    config.embedding.model = embedding_model
    return config


def _make_record(content: str = "some expertise content here") -> ExpertiseRecord:
    return ExpertiseRecord(
        type=ExpertiseType.CONVENTION,
        domain="test",
        content=content,
    )


def _make_pipeline(
    *,
    config: MagicMock | None = None,
    store: MagicMock | None = None,
    embedding_index: MagicMock | None = None,
) -> tuple[ExtractionPipeline, MagicMock, MagicMock | None]:
    if config is None:
        config = _make_config()
    if store is None:
        store = MagicMock()
    pipeline = ExtractionPipeline(store, embedding_index, config)
    return pipeline, store, embedding_index


class TestHeuristicOnlyMode:
    def test_heuristic_only_calls_heuristic_extractor(self) -> None:
        pipeline, store, _ = _make_pipeline()
        heuristic_record = _make_record("Always use dependency injection for testability.")
        store.insert.return_value = heuristic_record.id

        with patch.object(pipeline._heuristic, "extract", return_value=[heuristic_record]) as mock_extract:
            stats = pipeline.extract_from_text(
                "Always use dependency injection for testability.",
                mode="heuristic_only",
            )
            mock_extract.assert_called_once()

        assert stats.heuristic_extracted == 1
        assert stats.llm_extracted == 0

    def test_heuristic_only_does_not_call_llm(self) -> None:
        pipeline, store, _ = _make_pipeline()
        store.insert.return_value = "exp_test000001"

        with patch.object(pipeline, "_run_llm_extraction", return_value=[]) as mock_llm:
            pipeline.extract_from_text(
                "Always use dependency injection for testability.",
                mode="heuristic_only",
            )
            mock_llm.assert_not_called()


class TestFullMode:
    def test_full_mode_calls_both_extractors(self) -> None:
        pipeline, store, _ = _make_pipeline()
        heuristic_record = _make_record("Always use dependency injection.")
        llm_record = _make_record("Use repository pattern for data access layer.")
        store.insert.return_value = heuristic_record.id

        with patch.object(pipeline._heuristic, "extract", return_value=[heuristic_record]):
            with patch.object(pipeline, "_run_llm_extraction", return_value=[llm_record]):
                stats = pipeline.extract_from_text("Always use dependency injection.", mode="full")

        assert stats.heuristic_extracted == 1
        assert stats.llm_extracted == 1


class TestLlmOnlyMode:
    def test_llm_only_does_not_call_heuristic(self) -> None:
        pipeline, store, _ = _make_pipeline()
        llm_record = _make_record("Use circuit breaker pattern for external APIs.")
        store.insert.return_value = llm_record.id

        with patch.object(pipeline._heuristic, "extract", return_value=[]) as mock_heuristic:
            with patch.object(pipeline, "_run_llm_extraction", return_value=[llm_record]):
                stats = pipeline.extract_from_text("some text here", mode="llm_only")

        mock_heuristic.assert_not_called()
        assert stats.heuristic_extracted == 0
        assert stats.llm_extracted == 1


class TestDedupLogic:
    def test_similarity_above_threshold_reinforces(self) -> None:
        embedding_index = MagicMock()
        config = _make_config(dedup_threshold=0.95, flag_threshold=0.80)
        store = MagicMock()
        pipeline = ExtractionPipeline(store, embedding_index, config)

        existing_id = "exp_existing00001"
        embedding_index.find_similar.return_value = [(existing_id, 0.97)]

        record = _make_record("Always use type annotations in Python code.")
        result = pipeline._store_with_dedup(record)

        assert result.action == RecordAction.REINFORCED
        assert result.existing_id == existing_id
        store.validate_record.assert_called_once_with(existing_id)
        store.insert.assert_not_called()

    def test_similarity_at_threshold_reinforces(self) -> None:
        embedding_index = MagicMock()
        config = _make_config(dedup_threshold=0.95, flag_threshold=0.80)
        store = MagicMock()
        pipeline = ExtractionPipeline(store, embedding_index, config)

        existing_id = "exp_existing00002"
        embedding_index.find_similar.return_value = [(existing_id, 0.95)]

        record = _make_record("Always use type annotations in Python code.")
        result = pipeline._store_with_dedup(record)

        assert result.action == RecordAction.REINFORCED

    def test_similarity_between_thresholds_flags_duplicate(self) -> None:
        embedding_index = MagicMock()
        config = _make_config(dedup_threshold=0.95, flag_threshold=0.80)
        store = MagicMock()
        pipeline = ExtractionPipeline(store, embedding_index, config)

        existing_id = "exp_existing00003"
        embedding_index.find_similar.return_value = [(existing_id, 0.87)]

        record = _make_record("Always use type annotations in Python code.")
        result = pipeline._store_with_dedup(record)

        assert result.action == RecordAction.DUPLICATE_FLAGGED
        assert result.existing_id == existing_id
        store.insert.assert_not_called()

    def test_similarity_at_flag_threshold_flags_duplicate(self) -> None:
        embedding_index = MagicMock()
        config = _make_config(dedup_threshold=0.95, flag_threshold=0.80)
        store = MagicMock()
        pipeline = ExtractionPipeline(store, embedding_index, config)

        existing_id = "exp_existing00004"
        embedding_index.find_similar.return_value = [(existing_id, 0.80)]

        record = _make_record("Always use type annotations in Python code.")
        result = pipeline._store_with_dedup(record)

        assert result.action == RecordAction.DUPLICATE_FLAGGED

    def test_similarity_below_flag_threshold_creates_new(self) -> None:
        embedding_index = MagicMock()
        config = _make_config(dedup_threshold=0.95, flag_threshold=0.80)
        store = MagicMock()
        pipeline = ExtractionPipeline(store, embedding_index, config)

        existing_id = "exp_existing00005"
        embedding_index.find_similar.return_value = [(existing_id, 0.60)]

        record = _make_record("Always use type annotations in Python code.")
        result = pipeline._store_with_dedup(record)

        assert result.action == RecordAction.CREATED
        store.insert.assert_called_once_with(record)
        embedding_index.add.assert_called_once_with(record)

    def test_no_similar_found_creates_new(self) -> None:
        embedding_index = MagicMock()
        config = _make_config()
        store = MagicMock()
        pipeline = ExtractionPipeline(store, embedding_index, config)

        embedding_index.find_similar.return_value = []

        record = _make_record("Always use type annotations in Python code.")
        result = pipeline._store_with_dedup(record)

        assert result.action == RecordAction.CREATED
        store.insert.assert_called_once_with(record)

    def test_no_embedding_index_always_creates(self) -> None:
        config = _make_config()
        store = MagicMock()
        pipeline = ExtractionPipeline(store, None, config)

        record = _make_record("Always use type annotations in Python code.")
        result = pipeline._store_with_dedup(record)

        assert result.action == RecordAction.CREATED
        store.insert.assert_called_once_with(record)


class TestExtractBatch:
    def test_skips_conversations_with_text_under_50_chars(self) -> None:
        pipeline, store, _ = _make_pipeline()

        conversations = [
            {"full_text": "short", "conversation_id": "c1"},
            {"full_text": "  ", "conversation_id": "c2"},
            {"full_text": "", "conversation_id": "c3"},
        ]

        with patch.object(pipeline, "extract_from_text") as mock_extract:
            stats = pipeline.extract_batch(conversations)
            mock_extract.assert_not_called()

        assert stats.conversations_processed == 0

    def test_processes_conversations_with_sufficient_text(self) -> None:
        pipeline, store, _ = _make_pipeline()

        long_text = "Always use dependency injection for all services in this codebase."
        conversations = [
            {"full_text": long_text, "conversation_id": "c1"},
        ]

        expected_stats = ExtractionStats(conversations_processed=1, records_created=1)
        with patch.object(pipeline, "extract_from_text", return_value=expected_stats):
            stats = pipeline.extract_batch(conversations)

        assert stats.conversations_processed == 1
        assert stats.records_created == 1

    def test_aggregates_stats_from_multiple_conversations(self) -> None:
        pipeline, store, _ = _make_pipeline()

        long_text = "Always use dependency injection for testability in all new code."
        conversations = [
            {"full_text": long_text, "conversation_id": f"c{i}"}
            for i in range(3)
        ]

        per_conv_stats = ExtractionStats(
            conversations_processed=1,
            records_created=2,
            records_reinforced=1,
            records_flagged=0,
            heuristic_extracted=3,
            llm_extracted=0,
        )

        with patch.object(pipeline, "extract_from_text", return_value=per_conv_stats):
            stats = pipeline.extract_batch(conversations)

        assert stats.conversations_processed == 3
        assert stats.records_created == 6
        assert stats.records_reinforced == 3
        assert stats.heuristic_extracted == 9

    def test_errors_in_conversations_do_not_crash_batch(self) -> None:
        pipeline, store, _ = _make_pipeline()

        long_text = "Always use dependency injection for testability in services."
        conversations = [
            {"full_text": long_text, "conversation_id": "c1"},
            {"full_text": long_text, "conversation_id": "c2"},
        ]

        def side_effect(*args, **kwargs) -> ExtractionStats:
            conv_id = kwargs.get("conversation_id", "")
            if conv_id == "c1":
                raise RuntimeError("extraction failed unexpectedly")
            return ExtractionStats(conversations_processed=1, records_created=1)

        with patch.object(pipeline, "extract_from_text", side_effect=side_effect):
            stats = pipeline.extract_batch(conversations)

        assert stats.conversations_processed == 1
        assert len(stats.errors) == 1
        assert "c1" in stats.errors[0]

    def test_project_id_used_as_domain_when_present(self) -> None:
        pipeline, store, _ = _make_pipeline()

        long_text = "Always use dependency injection for testability in all services."
        conversations = [
            {"full_text": long_text, "conversation_id": "c1", "project_id": "my-project"},
        ]

        captured_kwargs: dict = {}

        def capture(*args, **kwargs) -> ExtractionStats:
            captured_kwargs.update(kwargs)
            return ExtractionStats(conversations_processed=1)

        with patch.object(pipeline, "extract_from_text", side_effect=capture):
            pipeline.extract_batch(conversations)

        assert captured_kwargs.get("domain") == "my-project"
        assert captured_kwargs.get("project") == "my-project"

    def test_default_domain_used_when_no_project_id(self) -> None:
        pipeline, store, _ = _make_pipeline()

        long_text = "Always use dependency injection for testability in all services."
        conversations = [{"full_text": long_text, "conversation_id": "c1"}]

        captured_kwargs: dict = {}

        def capture(*args, **kwargs) -> ExtractionStats:
            captured_kwargs.update(kwargs)
            return ExtractionStats(conversations_processed=1)

        with patch.object(pipeline, "extract_from_text", side_effect=capture):
            pipeline.extract_batch(conversations, default_domain="infra")

        assert captured_kwargs.get("domain") == "infra"


class TestCreatePipeline:
    def test_create_pipeline_returns_extraction_pipeline(self, tmp_path: Path) -> None:
        config = _make_config(expertise_enabled=True)

        with patch("searchat.expertise.pipeline.ExpertiseStore") as mock_store_cls:
            with patch("searchat.expertise.pipeline.ExpertiseEmbeddingIndex") as mock_index_cls:
                mock_store_cls.return_value = MagicMock()
                mock_index_cls.return_value = MagicMock()

                pipeline = create_pipeline(config, tmp_path)

        assert isinstance(pipeline, ExtractionPipeline)
        mock_store_cls.assert_called_once_with(tmp_path)

    def test_create_pipeline_with_expertise_enabled_creates_embedding_index(self, tmp_path: Path) -> None:
        config = _make_config(expertise_enabled=True, embedding_model="all-MiniLM-L6-v2")

        with patch("searchat.expertise.pipeline.ExpertiseStore"):
            with patch("searchat.expertise.pipeline.ExpertiseEmbeddingIndex") as mock_index_cls:
                mock_index_cls.return_value = MagicMock()
                pipeline = create_pipeline(config, tmp_path)

        mock_index_cls.assert_called_once_with(tmp_path, embedding_model="all-MiniLM-L6-v2")
        assert pipeline._embedding_index is not None

    def test_create_pipeline_with_expertise_disabled_skips_embedding_index(self, tmp_path: Path) -> None:
        config = _make_config(expertise_enabled=False)

        with patch("searchat.expertise.pipeline.ExpertiseStore"):
            with patch("searchat.expertise.pipeline.ExpertiseEmbeddingIndex") as mock_index_cls:
                pipeline = create_pipeline(config, tmp_path)

        mock_index_cls.assert_not_called()
        assert pipeline._embedding_index is None
