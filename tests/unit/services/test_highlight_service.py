"""Tests for searchat.services.highlight_service."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from searchat.services.highlight_service import _parse_terms, extract_highlight_terms


class TestParseTerms:
    """Tests for _parse_terms."""

    def test_valid_json_array(self):
        result = _parse_terms('["python", "async", "await"]')
        assert result == ["python", "async", "await"]

    def test_strips_markdown_fences(self):
        result = _parse_terms('```json\n["a", "b"]\n```')
        assert result == ["a", "b"]

    def test_strips_bare_backticks(self):
        result = _parse_terms('```\n["x", "y"]\n```')
        assert result == ["x", "y"]

    def test_deduplicates_case_insensitive(self):
        result = _parse_terms('["Python", "python", "PYTHON"]')
        assert result == ["Python"]

    def test_skips_empty_strings(self):
        result = _parse_terms('["a", "", "b", "  "]')
        assert result == ["a", "b"]

    def test_truncates_to_8(self):
        terms = [f"term{i}" for i in range(12)]
        import json
        result = _parse_terms(json.dumps(terms))
        assert len(result) == 8

    def test_rejects_invalid_json(self):
        with pytest.raises(ValueError, match="valid JSON array"):
            _parse_terms("not json at all")

    def test_rejects_non_array(self):
        with pytest.raises(ValueError, match="must be a JSON array"):
            _parse_terms('{"key": "value"}')

    def test_rejects_non_string_items(self):
        with pytest.raises(ValueError, match="strings only"):
            _parse_terms('[1, 2, 3]')

    def test_rejects_all_empty(self):
        with pytest.raises(ValueError, match="no usable terms"):
            _parse_terms('["", "  "]')


class TestExtractHighlightTerms:
    """Tests for extract_highlight_terms end-to-end."""

    def test_extracts_terms_via_llm(self):
        llm_config = SimpleNamespace(
            openai_model="gpt-4.1-mini",
            ollama_model="llama3",
        )
        config = SimpleNamespace(llm=llm_config)

        with patch(
            "searchat.services.highlight_service.LLMService"
        ) as MockLLMService:
            mock_instance = MockLLMService.return_value
            mock_instance.completion.return_value = '["python", "async", "coroutines"]'

            result = extract_highlight_terms(
                query="how does python async work",
                provider="openai",
                model_name="gpt-4.1-mini",
                config=config,
            )

        assert result == ["python", "async", "coroutines"]
        mock_instance.completion.assert_called_once()
