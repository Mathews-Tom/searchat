"""Additional tests for HeuristicExtractor — edge cases and fallback paths."""
from __future__ import annotations

import pytest

from searchat.expertise.extractor import HeuristicExtractor, _extract_sentence
from searchat.expertise.models import ExpertiseType


class TestExtractSentence:
    def test_extracts_sentence_containing_match(self):
        text = "First sentence. The convention is to use snake_case. Last sentence."
        match_start = text.index("The convention")
        match_end = match_start + len("The convention is")
        result = _extract_sentence(text, match_start, match_end)
        assert "convention" in result

    def test_fallback_window_when_sentence_not_found(self):
        # Pathological text where sentence splitting fails to locate match
        text = "x" * 500
        result = _extract_sentence(text, 200, 210)
        assert len(result) > 0  # Fallback window should produce something

    def test_paragraph_split(self):
        text = "First paragraph.\n\nThe fix was to increase the buffer.\n\nThird paragraph."
        match_start = text.index("The fix")
        match_end = match_start + len("The fix was")
        result = _extract_sentence(text, match_start, match_end)
        assert "fix" in result


class TestHeuristicExtractorEdgeCases:
    def test_empty_text_returns_empty(self):
        ext = HeuristicExtractor()
        assert ext.extract("") == []
        assert ext.extract("   ") == []

    def test_no_signals_returns_empty(self):
        ext = HeuristicExtractor()
        result = ext.extract("Lorem ipsum dolor sit amet, consectetur adipiscing elit.")
        assert result == []

    def test_deduplicates_within_run(self):
        ext = HeuristicExtractor()
        # Same sentence matched by two signals should only produce one record
        text = "The convention is to always use type annotations in your Python code."
        result = ext.extract(text)
        contents = [r.content for r in result]
        # Each unique content should appear only once
        assert len(contents) == len(set(c[:100].lower() for c in contents))

    def test_skips_short_content(self):
        ext = HeuristicExtractor()
        # Match in very short context (< 10 chars after extraction)
        text = "must not"
        result = ext.extract(text)
        assert result == []

    def test_sets_severity_for_failure_type(self):
        ext = HeuristicExtractor()
        text = "The fix was to increase the buffer size to handle larger payloads."
        result = ext.extract(text)
        failures = [r for r in result if r.type == ExpertiseType.FAILURE]
        assert len(failures) >= 1
        assert failures[0].severity is not None

    def test_sets_severity_for_boundary_type(self):
        ext = HeuristicExtractor()
        text = "This is a hard requirement that must be satisfied for compliance."
        result = ext.extract(text)
        boundaries = [r for r in result if r.type == ExpertiseType.BOUNDARY]
        assert len(boundaries) >= 1
        assert boundaries[0].severity is not None

    def test_convention_signal_detected(self):
        ext = HeuristicExtractor()
        text = "We standardize on using Black for code formatting across all projects."
        result = ext.extract(text)
        assert any(r.type == ExpertiseType.CONVENTION for r in result)

    def test_decision_signal_detected(self):
        ext = HeuristicExtractor()
        text = "We decided to use PostgreSQL over MongoDB for better ACID compliance."
        result = ext.extract(text)
        assert any(r.type == ExpertiseType.DECISION for r in result)

    def test_insight_signal_detected(self):
        ext = HeuristicExtractor()
        text = "It is worth noting that the latency improved significantly after caching."
        result = ext.extract(text)
        assert any(r.type == ExpertiseType.INSIGHT for r in result)

    def test_pattern_signal_detected(self):
        ext = HeuristicExtractor()
        text = "The pattern is to use factory functions for all service instantiation."
        result = ext.extract(text)
        assert any(r.type == ExpertiseType.PATTERN for r in result)

    def test_source_agent_set(self):
        ext = HeuristicExtractor()
        text = "The convention is to always use type annotations in Python code."
        result = ext.extract(text)
        assert all(r.source_agent == "heuristic-extractor" for r in result)

    def test_domain_and_project_passed_through(self):
        ext = HeuristicExtractor()
        text = "The convention is to always use type annotations in Python code."
        result = ext.extract(text, domain="python", project="myproj")
        assert all(r.domain == "python" for r in result)
        assert all(r.project == "myproj" for r in result)
