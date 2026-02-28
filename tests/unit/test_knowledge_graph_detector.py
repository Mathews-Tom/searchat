"""Tests for ContradictionDetector with mocked embeddings and NLI."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from searchat.expertise.models import ExpertiseRecord, ExpertiseType
from searchat.expertise.store import ExpertiseStore
from searchat.knowledge_graph.detector import ContradictionDetector
from searchat.knowledge_graph.models import ContradictionCandidate


def _make_record(
    content: str,
    domain: str = "test",
    rec_type: ExpertiseType = ExpertiseType.PATTERN,
    record_id: str | None = None,
) -> ExpertiseRecord:
    r = ExpertiseRecord(type=rec_type, domain=domain, content=content)
    if record_id is not None:
        r.id = record_id
    return r


@pytest.fixture
def expertise_store(tmp_path: Path) -> ExpertiseStore:
    return ExpertiseStore(data_dir=tmp_path)


@pytest.fixture
def mock_embedding_index() -> MagicMock:
    idx = MagicMock()
    idx.search.return_value = []
    return idx


class TestStage1OnlyMode:
    """Tests when NLI is unavailable — Stage 1 only."""

    def test_no_candidates_when_no_similar_records(
        self,
        expertise_store: ExpertiseStore,
        mock_embedding_index: MagicMock,
    ) -> None:
        detector = ContradictionDetector()
        record = _make_record("use snake_case for variables")
        mock_embedding_index.search.return_value = []

        candidates = detector.check_record(record, expertise_store, mock_embedding_index)
        assert candidates == []

    def test_stage1_returns_candidates_when_nli_unavailable(
        self,
        expertise_store: ExpertiseStore,
        mock_embedding_index: MagicMock,
    ) -> None:
        record_a = _make_record("always use type hints", record_id="exp_a001")
        record_b = _make_record("never use type hints", record_id="exp_b001")
        expertise_store.insert(record_b)

        mock_embedding_index.search.return_value = [(record_b.id, 0.85)]

        detector = ContradictionDetector()
        # Force NLI unavailable
        detector._nli_available = False

        candidates = detector.check_record(record_a, expertise_store, mock_embedding_index)
        assert len(candidates) == 1
        assert candidates[0].record_id_a == record_a.id
        assert candidates[0].record_id_b == record_b.id
        assert candidates[0].similarity_score == 0.85
        assert candidates[0].nli_available is False

    def test_stage1_excludes_self(
        self,
        expertise_store: ExpertiseStore,
        mock_embedding_index: MagicMock,
    ) -> None:
        record = _make_record("always use type hints", record_id="exp_self")
        expertise_store.insert(record)

        # Search returns the record itself
        mock_embedding_index.search.return_value = [(record.id, 0.99)]

        detector = ContradictionDetector()
        detector._nli_available = False

        candidates = detector.check_record(record, expertise_store, mock_embedding_index)
        assert candidates == []

    def test_stage1_excludes_inactive_records(
        self,
        expertise_store: ExpertiseStore,
        mock_embedding_index: MagicMock,
    ) -> None:
        record_a = _make_record("always use type hints", record_id="exp_a002")
        record_b = _make_record("never use type hints", record_id="exp_b002")
        expertise_store.insert(record_b)
        expertise_store.soft_delete(record_b.id)

        mock_embedding_index.search.return_value = [(record_b.id, 0.85)]

        detector = ContradictionDetector()
        detector._nli_available = False

        candidates = detector.check_record(record_a, expertise_store, mock_embedding_index)
        assert candidates == []

    def test_stage1_skips_records_not_in_store(
        self,
        expertise_store: ExpertiseStore,
        mock_embedding_index: MagicMock,
    ) -> None:
        record = _make_record("use type hints", record_id="exp_main")
        # Search returns an ID not in the store
        mock_embedding_index.search.return_value = [("exp_ghost_id", 0.88)]

        detector = ContradictionDetector()
        detector._nli_available = False

        candidates = detector.check_record(record, expertise_store, mock_embedding_index)
        assert candidates == []


class TestStage2NLIMode:
    """Tests when NLI cross-encoder is available (mocked)."""

    def _make_mock_cross_encoder(self, contradiction_score: float = 0.85) -> MagicMock:
        mock_ce = MagicMock()
        mock_ce.predict.return_value = np.array([[contradiction_score, 0.05, 0.10]])
        return mock_ce

    def test_contradiction_flagged_above_threshold(
        self,
        expertise_store: ExpertiseStore,
        mock_embedding_index: MagicMock,
    ) -> None:
        record_a = _make_record("always use type hints", record_id="exp_nli_a")
        record_b = _make_record("never use type hints", record_id="exp_nli_b")
        expertise_store.insert(record_b)

        mock_embedding_index.search.return_value = [(record_b.id, 0.82)]

        detector = ContradictionDetector()
        detector._nli_available = True
        detector._cross_encoder = self._make_mock_cross_encoder(contradiction_score=0.85)

        candidates = detector.check_record(record_a, expertise_store, mock_embedding_index)
        assert len(candidates) == 1
        assert candidates[0].contradiction_score == pytest.approx(0.85, abs=1e-3)
        assert candidates[0].nli_available is True

    def test_contradiction_not_flagged_below_threshold(
        self,
        expertise_store: ExpertiseStore,
        mock_embedding_index: MagicMock,
    ) -> None:
        record_a = _make_record("use type hints when possible", record_id="exp_nli_c")
        record_b = _make_record("type hints are recommended", record_id="exp_nli_d")
        expertise_store.insert(record_b)

        mock_embedding_index.search.return_value = [(record_b.id, 0.78)]

        detector = ContradictionDetector()
        detector._nli_available = True
        detector._cross_encoder = self._make_mock_cross_encoder(contradiction_score=0.30)

        candidates = detector.check_record(record_a, expertise_store, mock_embedding_index)
        assert candidates == []

    def test_nli_exception_falls_back_to_stage1(
        self,
        expertise_store: ExpertiseStore,
        mock_embedding_index: MagicMock,
    ) -> None:
        record_a = _make_record("use type hints", record_id="exp_nli_e")
        record_b = _make_record("avoid type hints", record_id="exp_nli_f")
        expertise_store.insert(record_b)

        mock_embedding_index.search.return_value = [(record_b.id, 0.80)]

        mock_ce = MagicMock()
        mock_ce.predict.side_effect = RuntimeError("model error")

        detector = ContradictionDetector()
        detector._nli_available = True
        detector._cross_encoder = mock_ce

        candidates = detector.check_record(record_a, expertise_store, mock_embedding_index)
        assert len(candidates) == 1
        assert candidates[0].nli_available is False

    def test_multiple_candidates_filtered_by_nli(
        self,
        expertise_store: ExpertiseStore,
        mock_embedding_index: MagicMock,
    ) -> None:
        record_a = _make_record("use tabs for indentation", record_id="exp_main_tabs")
        record_b = _make_record("never use tabs", record_id="exp_no_tabs")
        record_c = _make_record("tabs are an option", record_id="exp_tabs_option")
        expertise_store.insert(record_b)
        expertise_store.insert(record_c)

        mock_embedding_index.search.return_value = [
            (record_b.id, 0.88),
            (record_c.id, 0.77),
        ]

        # First pair: contradiction; Second pair: entailment
        mock_ce = MagicMock()
        mock_ce.predict.side_effect = [
            np.array([[0.90, 0.05, 0.05]]),
            np.array([[0.10, 0.85, 0.05]]),
        ]

        detector = ContradictionDetector()
        detector._nli_available = True
        detector._cross_encoder = mock_ce

        candidates = detector.check_record(record_a, expertise_store, mock_embedding_index)
        assert len(candidates) == 1
        assert candidates[0].record_id_b == record_b.id


class TestNLILazyLoad:
    def test_nli_unavailable_when_import_fails(self) -> None:
        detector = ContradictionDetector()
        with patch("searchat.knowledge_graph.detector.ContradictionDetector._ensure_cross_encoder", return_value=False):
            assert detector._ensure_cross_encoder() is False

    def test_threshold_constants(self) -> None:
        assert ContradictionDetector.SIMILARITY_THRESHOLD == 0.75
        assert ContradictionDetector.CONTRADICTION_THRESHOLD == 0.70
        assert "nli-deberta" in ContradictionDetector.NLI_MODEL

    def test_custom_nli_model_name(self) -> None:
        detector = ContradictionDetector(nli_model="custom/model")
        assert detector._nli_model_name == "custom/model"
