"""Tests for NLI branch and edge cases in ContradictionDetector."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from searchat.expertise.models import ExpertiseRecord, ExpertiseType
from searchat.knowledge_graph.detector import ContradictionDetector


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_record(
    record_id: str = "rec-1",
    content: str = "Use tabs for indentation",
) -> ExpertiseRecord:
    r = ExpertiseRecord(
        type=ExpertiseType.CONVENTION,
        domain="python",
        content=content,
        created_at=_utcnow(),
        last_validated=_utcnow(),
    )
    object.__setattr__(r, "id", record_id)
    return r


class TestEnsureCrossEncoder:
    def test_returns_true_when_available(self):
        detector = ContradictionDetector()

        fake_ce = MagicMock()
        with patch("searchat.knowledge_graph.detector.CrossEncoder", fake_ce, create=True):
            # Patch the import inside the method
            import searchat.knowledge_graph.detector as det_mod
            original = det_mod.ContradictionDetector._ensure_cross_encoder

            def _patched_ensure(self):
                if self._nli_available is not None:
                    return self._nli_available
                self._cross_encoder = MagicMock()
                self._nli_available = True
                return True

            det_mod.ContradictionDetector._ensure_cross_encoder = _patched_ensure
            try:
                assert detector._ensure_cross_encoder() is True
                assert detector._nli_available is True
                # Second call returns cached
                assert detector._ensure_cross_encoder() is True
            finally:
                det_mod.ContradictionDetector._ensure_cross_encoder = original

    def test_returns_false_when_import_fails(self):
        detector = ContradictionDetector()
        # Force NLI unavailable
        detector._nli_available = False

        assert detector._ensure_cross_encoder() is False

    def test_caches_availability(self):
        detector = ContradictionDetector()
        detector._nli_available = True
        detector._cross_encoder = MagicMock()

        # Should return cached value without re-importing
        assert detector._ensure_cross_encoder() is True


class TestStage2Nli:
    def test_returns_none_when_cross_encoder_unavailable(self):
        detector = ContradictionDetector()
        detector._nli_available = False

        rec_a = _make_record("a", "Use tabs")
        rec_b = _make_record("b", "Use spaces")

        result = detector._stage2_nli(rec_a, rec_b)
        assert result is None

    def test_returns_scores_with_3_labels(self):
        detector = ContradictionDetector()
        detector._nli_available = True

        import numpy as np

        fake_scores = np.array([[0.85, 0.05, 0.10]])  # [contradiction, entailment, neutral]
        detector._cross_encoder = MagicMock()
        detector._cross_encoder.predict.return_value = fake_scores

        rec_a = _make_record("a", "Use tabs")
        rec_b = _make_record("b", "Use spaces")

        result = detector._stage2_nli(rec_a, rec_b)
        assert result is not None
        assert len(result) == 3
        assert result[0] == pytest.approx(0.85, abs=0.01)

    def test_returns_none_on_prediction_error(self):
        detector = ContradictionDetector()
        detector._nli_available = True
        detector._cross_encoder = MagicMock()
        detector._cross_encoder.predict.side_effect = RuntimeError("model error")

        rec_a = _make_record("a", "Use tabs")
        rec_b = _make_record("b", "Use spaces")

        result = detector._stage2_nli(rec_a, rec_b)
        assert result is None


class TestCheckRecord:
    def test_returns_empty_when_no_stage1_candidates(self):
        detector = ContradictionDetector()
        rec = _make_record("r", "Unique content")
        store = MagicMock()
        embedding_index = MagicMock()
        embedding_index.search.return_value = []

        result = detector.check_record(rec, store, embedding_index)
        assert result == []

    def test_skips_self_in_stage1(self):
        detector = ContradictionDetector()
        rec = _make_record("self-rec", "Some content")
        store = MagicMock()

        # Embedding index returns self
        embedding_index = MagicMock()
        embedding_index.search.return_value = [("self-rec", 0.99)]

        detector._nli_available = False
        result = detector.check_record(rec, store, embedding_index)
        assert result == []

    def test_stage1_only_when_nli_unavailable(self):
        detector = ContradictionDetector()
        detector._nli_available = False

        rec = _make_record("rec-1", "Use tabs for indentation")
        other = _make_record("rec-2", "Use spaces for indentation")

        store = MagicMock()
        store.get.return_value = other

        embedding_index = MagicMock()
        embedding_index.search.return_value = [("rec-2", 0.85)]

        result = detector.check_record(rec, store, embedding_index)
        assert len(result) == 1
        assert result[0].nli_available is False
        assert result[0].similarity_score == 0.85

    def test_skips_inactive_records(self):
        detector = ContradictionDetector()
        detector._nli_available = False

        rec = _make_record("rec-1")
        inactive = _make_record("rec-2")
        object.__setattr__(inactive, "is_active", False)

        store = MagicMock()
        store.get.return_value = inactive

        embedding_index = MagicMock()
        embedding_index.search.return_value = [("rec-2", 0.9)]

        result = detector.check_record(rec, store, embedding_index)
        assert result == []

    def test_skips_none_records(self):
        detector = ContradictionDetector()
        detector._nli_available = False

        rec = _make_record("rec-1")
        store = MagicMock()
        store.get.return_value = None

        embedding_index = MagicMock()
        embedding_index.search.return_value = [("deleted-rec", 0.9)]

        result = detector.check_record(rec, store, embedding_index)
        assert result == []

    def test_stage2_filters_by_threshold(self):
        """Only candidates above CONTRADICTION_THRESHOLD should be included."""
        detector = ContradictionDetector()
        detector._nli_available = True

        import numpy as np

        # Below threshold — should not be included
        detector._cross_encoder = MagicMock()
        detector._cross_encoder.predict.return_value = np.array([[0.3, 0.5, 0.2]])

        rec = _make_record("rec-1", "Use tabs")
        other = _make_record("rec-2", "Use spaces")

        store = MagicMock()
        store.get.return_value = other

        embedding_index = MagicMock()
        embedding_index.search.return_value = [("rec-2", 0.85)]

        result = detector.check_record(rec, store, embedding_index)
        assert result == []

    def test_stage2_includes_above_threshold(self):
        detector = ContradictionDetector()
        detector._nli_available = True

        import numpy as np

        detector._cross_encoder = MagicMock()
        detector._cross_encoder.predict.return_value = np.array([[0.85, 0.05, 0.10]])

        rec = _make_record("rec-1", "Use tabs")
        other = _make_record("rec-2", "Use spaces")

        store = MagicMock()
        store.get.return_value = other

        embedding_index = MagicMock()
        embedding_index.search.return_value = [("rec-2", 0.85)]

        result = detector.check_record(rec, store, embedding_index)
        assert len(result) == 1
        assert result[0].nli_available is True
        assert result[0].contradiction_score == pytest.approx(0.85, abs=0.01)

    def test_nli_returns_none_falls_back_to_stage1_candidate(self):
        detector = ContradictionDetector()
        detector._nli_available = True
        detector._cross_encoder = MagicMock()
        detector._cross_encoder.predict.side_effect = RuntimeError("model error")

        rec = _make_record("rec-1", "Use tabs")
        other = _make_record("rec-2", "Use spaces")

        store = MagicMock()
        store.get.return_value = other

        embedding_index = MagicMock()
        embedding_index.search.return_value = [("rec-2", 0.85)]

        result = detector.check_record(rec, store, embedding_index)
        assert len(result) == 1
        assert result[0].nli_available is False
