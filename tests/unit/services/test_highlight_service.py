"""Tests for searchat.services.highlight_service._parse_terms."""
from __future__ import annotations

import pytest

from searchat.services.highlight_service import _parse_terms


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
