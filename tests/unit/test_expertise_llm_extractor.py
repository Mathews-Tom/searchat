"""Tests for LLMExtractor — mocked LLMService calls."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from searchat.expertise.llm_extractor import ExtractionError, LLMExtractor
from searchat.expertise.models import ExpertiseSeverity, ExpertiseType
from searchat.services.llm_service import LLMServiceError


def _make_extractor() -> tuple[LLMExtractor, MagicMock]:
    """Return an LLMExtractor and its patched LLMService instance."""
    llm_config = MagicMock()
    llm_config.default_provider = "openai"

    with patch("searchat.expertise.llm_extractor.LLMService") as mock_cls:
        mock_service = MagicMock()
        mock_cls.return_value = mock_service
        extractor = LLMExtractor(llm_config)

    return extractor, mock_service


class TestValidResponse:
    def test_valid_json_array_produces_records(self) -> None:
        extractor, mock_service = _make_extractor()
        payload = [
            {
                "type": "convention",
                "domain": "python",
                "content": "Always use type annotations for public functions.",
                "confidence": 0.85,
            }
        ]
        mock_service.completion.return_value = json.dumps(payload)

        records = extractor.extract("some conversation text", domain="python")

        assert len(records) == 1
        assert records[0].type == ExpertiseType.CONVENTION
        assert records[0].domain == "python"
        assert records[0].content == "Always use type annotations for public functions."

    def test_empty_array_returns_no_records(self) -> None:
        extractor, mock_service = _make_extractor()
        mock_service.completion.return_value = "[]"

        records = extractor.extract("some text")
        assert records == []

    def test_multiple_records_all_parsed(self) -> None:
        extractor, mock_service = _make_extractor()
        payload = [
            {"type": "convention", "domain": "api", "content": "Use versioned endpoints.", "confidence": 0.8},
            {"type": "failure", "domain": "api", "content": "Missing auth check caused data leak.", "confidence": 0.9, "severity": "high"},
        ]
        mock_service.completion.return_value = json.dumps(payload)

        records = extractor.extract("text")
        assert len(records) == 2


class TestConfidenceClamping:
    def test_confidence_below_min_clamped_to_07(self) -> None:
        extractor, mock_service = _make_extractor()
        payload = [{"type": "pattern", "domain": "db", "content": "Use transactions for multi-step writes.", "confidence": 0.3}]
        mock_service.completion.return_value = json.dumps(payload)

        records = extractor.extract("text")
        assert records[0].confidence == pytest.approx(0.7)

    def test_confidence_above_max_clamped_to_09(self) -> None:
        extractor, mock_service = _make_extractor()
        payload = [{"type": "decision", "domain": "arch", "content": "We chose event sourcing for audit trail.", "confidence": 0.99}]
        mock_service.completion.return_value = json.dumps(payload)

        records = extractor.extract("text")
        assert records[0].confidence == pytest.approx(0.9)

    def test_confidence_within_range_unchanged(self) -> None:
        extractor, mock_service = _make_extractor()
        payload = [{"type": "insight", "domain": "perf", "content": "Batch inserts reduce overhead by 60%.", "confidence": 0.8}]
        mock_service.completion.return_value = json.dumps(payload)

        records = extractor.extract("text")
        assert records[0].confidence == pytest.approx(0.8)

    def test_confidence_at_min_boundary_unchanged(self) -> None:
        extractor, mock_service = _make_extractor()
        payload = [{"type": "convention", "domain": "test", "content": "Always mock external services in unit tests.", "confidence": 0.7}]
        mock_service.completion.return_value = json.dumps(payload)

        records = extractor.extract("text")
        assert records[0].confidence == pytest.approx(0.7)

    def test_confidence_at_max_boundary_unchanged(self) -> None:
        extractor, mock_service = _make_extractor()
        payload = [{"type": "boundary", "domain": "sec", "content": "Never expose credentials in logs.", "confidence": 0.9}]
        mock_service.completion.return_value = json.dumps(payload)

        records = extractor.extract("text")
        assert records[0].confidence == pytest.approx(0.9)


class TestExtractionErrors:
    def test_non_json_response_raises_extraction_error(self) -> None:
        extractor, mock_service = _make_extractor()
        mock_service.completion.return_value = "This is not JSON at all."

        with pytest.raises(ExtractionError, match="non-JSON"):
            extractor.extract("text")

    def test_json_object_not_array_raises_extraction_error(self) -> None:
        extractor, mock_service = _make_extractor()
        mock_service.completion.return_value = json.dumps({"type": "convention", "content": "x"})

        with pytest.raises(ExtractionError, match="JSON array"):
            extractor.extract("text")

    def test_missing_type_field_raises_extraction_error(self) -> None:
        extractor, mock_service = _make_extractor()
        payload = [{"domain": "api", "content": "Always validate inputs.", "confidence": 0.8}]
        mock_service.completion.return_value = json.dumps(payload)

        with pytest.raises(ExtractionError, match="type"):
            extractor.extract("text")

    def test_invalid_type_value_raises_extraction_error(self) -> None:
        extractor, mock_service = _make_extractor()
        payload = [{"type": "unknown_type", "domain": "api", "content": "Always validate inputs.", "confidence": 0.8}]
        mock_service.completion.return_value = json.dumps(payload)

        with pytest.raises(ExtractionError, match="type"):
            extractor.extract("text")

    def test_missing_content_field_raises_extraction_error(self) -> None:
        extractor, mock_service = _make_extractor()
        payload = [{"type": "convention", "domain": "api", "confidence": 0.8}]
        mock_service.completion.return_value = json.dumps(payload)

        with pytest.raises(ExtractionError, match="content"):
            extractor.extract("text")

    def test_empty_content_raises_extraction_error(self) -> None:
        extractor, mock_service = _make_extractor()
        payload = [{"type": "convention", "domain": "api", "content": "", "confidence": 0.8}]
        mock_service.completion.return_value = json.dumps(payload)

        with pytest.raises(ExtractionError, match="content"):
            extractor.extract("text")

    def test_llm_service_error_raises_extraction_error(self) -> None:
        extractor, mock_service = _make_extractor()
        mock_service.completion.side_effect = LLMServiceError("provider down")

        with pytest.raises(ExtractionError, match="unavailable"):
            extractor.extract("text")


class TestSourceAgent:
    def test_source_agent_is_llm_extractor(self) -> None:
        extractor, mock_service = _make_extractor()
        payload = [{"type": "pattern", "domain": "api", "content": "Use idempotency keys for POST endpoints.", "confidence": 0.8}]
        mock_service.completion.return_value = json.dumps(payload)

        records = extractor.extract("text")
        assert records[0].source_agent == "llm-extractor"


class TestSeverityParsing:
    def test_valid_severity_preserved(self) -> None:
        extractor, mock_service = _make_extractor()
        for severity_val in ("low", "medium", "high", "critical"):
            payload = [
                {
                    "type": "failure",
                    "domain": "db",
                    "content": f"A {severity_val} severity failure was found.",
                    "confidence": 0.8,
                    "severity": severity_val,
                }
            ]
            mock_service.completion.return_value = json.dumps(payload)
            records = extractor.extract("text")
            assert records[0].severity == ExpertiseSeverity(severity_val)

    def test_invalid_severity_becomes_none(self) -> None:
        extractor, mock_service = _make_extractor()
        payload = [
            {
                "type": "failure",
                "domain": "db",
                "content": "Some failure occurred in the system.",
                "confidence": 0.8,
                "severity": "catastrophic",
            }
        ]
        mock_service.completion.return_value = json.dumps(payload)

        records = extractor.extract("text")
        assert records[0].severity is None

    def test_missing_severity_is_none(self) -> None:
        extractor, mock_service = _make_extractor()
        payload = [{"type": "convention", "domain": "test", "content": "Always write unit tests first.", "confidence": 0.8}]
        mock_service.completion.return_value = json.dumps(payload)

        records = extractor.extract("text")
        assert records[0].severity is None


class TestDomainFallback:
    def test_domain_from_item_takes_precedence(self) -> None:
        extractor, mock_service = _make_extractor()
        payload = [{"type": "convention", "domain": "frontend", "content": "Use React hooks over class components.", "confidence": 0.8}]
        mock_service.completion.return_value = json.dumps(payload)

        records = extractor.extract("text", domain="backend")
        assert records[0].domain == "frontend"

    def test_fallback_domain_used_when_item_domain_missing(self) -> None:
        extractor, mock_service = _make_extractor()
        payload = [{"type": "convention", "content": "Use React hooks over class components.", "confidence": 0.8}]
        mock_service.completion.return_value = json.dumps(payload)

        records = extractor.extract("text", domain="backend")
        assert records[0].domain == "backend"

    def test_fallback_domain_used_when_item_domain_empty(self) -> None:
        extractor, mock_service = _make_extractor()
        payload = [{"type": "convention", "domain": "", "content": "Use meaningful commit messages always.", "confidence": 0.8}]
        mock_service.completion.return_value = json.dumps(payload)

        records = extractor.extract("text", domain="git")
        assert records[0].domain == "git"

    def test_project_passed_through_to_records(self) -> None:
        extractor, mock_service = _make_extractor()
        payload = [{"type": "decision", "domain": "arch", "content": "We chose event-driven architecture.", "confidence": 0.8}]
        mock_service.completion.return_value = json.dumps(payload)

        records = extractor.extract("text", project="my-project")
        assert records[0].project == "my-project"


class TestExtractBatch:
    def test_extract_batch_processes_all_tuples(self) -> None:
        extractor, mock_service = _make_extractor()
        payload_a = [{"type": "convention", "domain": "python", "content": "Always use type hints consistently.", "confidence": 0.8}]
        payload_b = [{"type": "pattern", "domain": "api", "content": "Use REST resource naming for endpoints.", "confidence": 0.8}]
        mock_service.completion.side_effect = [
            json.dumps(payload_a),
            json.dumps(payload_b),
        ]

        texts = [
            ("first conversation text", "python", None),
            ("second conversation text", "api", "proj-x"),
        ]
        records = extractor.extract_batch(texts)
        assert len(records) == 2
        assert records[0].type == ExpertiseType.CONVENTION
        assert records[1].type == ExpertiseType.PATTERN

    def test_extract_batch_respects_batch_size(self) -> None:
        extractor, mock_service = _make_extractor()
        single_item = [{"type": "insight", "domain": "perf", "content": "Caching reduces API response time.", "confidence": 0.8}]
        mock_service.completion.return_value = json.dumps(single_item)

        texts = [("text", "general", None)] * 3
        records = extractor.extract_batch(texts, batch_size=2)
        assert len(records) == 3
        assert mock_service.completion.call_count == 3

    def test_extract_batch_empty_input(self) -> None:
        extractor, mock_service = _make_extractor()
        records = extractor.extract_batch([])
        assert records == []
        mock_service.completion.assert_not_called()
