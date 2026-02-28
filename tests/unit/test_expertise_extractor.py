"""Tests for HeuristicExtractor regex-based expertise extraction."""
from __future__ import annotations

import pytest

from searchat.expertise.extractor import HeuristicExtractor
from searchat.expertise.models import ExpertiseSeverity, ExpertiseType


@pytest.fixture
def extractor() -> HeuristicExtractor:
    return HeuristicExtractor()


class TestEmptyInput:
    def test_empty_string_returns_no_records(self, extractor: HeuristicExtractor) -> None:
        assert extractor.extract("") == []

    def test_whitespace_only_returns_no_records(self, extractor: HeuristicExtractor) -> None:
        assert extractor.extract("   \n\t  ") == []

    def test_none_like_empty_string_returns_no_records(self, extractor: HeuristicExtractor) -> None:
        assert extractor.extract("") == []


class TestConventionSignals:
    def test_always_use_triggers_convention(self, extractor: HeuristicExtractor) -> None:
        records = extractor.extract("Always use type hints in Python functions.")
        types = [r.type for r in records]
        assert ExpertiseType.CONVENTION in types

    def test_never_do_triggers_convention(self, extractor: HeuristicExtractor) -> None:
        records = extractor.extract("Never do inline SQL concatenation in user inputs.")
        types = [r.type for r in records]
        assert ExpertiseType.CONVENTION in types

    def test_the_convention_is_triggers_convention(self, extractor: HeuristicExtractor) -> None:
        records = extractor.extract("The convention is to prefix private methods with underscore.")
        types = [r.type for r in records]
        assert ExpertiseType.CONVENTION in types

    def test_rule_of_thumb_triggers_convention(self, extractor: HeuristicExtractor) -> None:
        records = extractor.extract("The rule of thumb is to keep functions under 50 lines.")
        types = [r.type for r in records]
        assert ExpertiseType.CONVENTION in types


class TestPatternSignals:
    def test_the_pattern_is_triggers_pattern(self, extractor: HeuristicExtractor) -> None:
        records = extractor.extract("The pattern is to use repository abstraction over raw ORM.")
        types = [r.type for r in records]
        assert ExpertiseType.PATTERN in types

    def test_the_approach_we_use_triggers_pattern(self, extractor: HeuristicExtractor) -> None:
        records = extractor.extract("The approach we use for pagination is cursor-based.")
        types = [r.type for r in records]
        assert ExpertiseType.PATTERN in types

    def test_the_standard_way_triggers_pattern(self, extractor: HeuristicExtractor) -> None:
        records = extractor.extract("The standard way to handle errors is with Result types.")
        types = [r.type for r in records]
        assert ExpertiseType.PATTERN in types


class TestFailureSignals:
    def test_root_cause_triggers_failure(self, extractor: HeuristicExtractor) -> None:
        records = extractor.extract("The root cause was a missing database index on user_id.")
        types = [r.type for r in records]
        assert ExpertiseType.FAILURE in types

    def test_the_fix_was_triggers_failure(self, extractor: HeuristicExtractor) -> None:
        records = extractor.extract("The fix was to add a retry with exponential backoff.")
        types = [r.type for r in records]
        assert ExpertiseType.FAILURE in types

    def test_the_bug_was_triggers_failure(self, extractor: HeuristicExtractor) -> None:
        records = extractor.extract("The bug was caused by off-by-one in slice indexing.")
        types = [r.type for r in records]
        assert ExpertiseType.FAILURE in types

    def test_lesson_learned_triggers_failure(self, extractor: HeuristicExtractor) -> None:
        records = extractor.extract("Lesson learned from this incident: always validate env vars at startup.")
        types = [r.type for r in records]
        assert ExpertiseType.FAILURE in types


class TestDecisionSignals:
    def test_we_decided_to_triggers_decision(self, extractor: HeuristicExtractor) -> None:
        records = extractor.extract("We decided to migrate away from REST to GraphQL.")
        types = [r.type for r in records]
        assert ExpertiseType.DECISION in types

    def test_we_chose_triggers_decision(self, extractor: HeuristicExtractor) -> None:
        records = extractor.extract("We chose PostgreSQL over MongoDB for relational data needs.")
        types = [r.type for r in records]
        assert ExpertiseType.DECISION in types

    def test_the_rationale_is_triggers_decision(self, extractor: HeuristicExtractor) -> None:
        records = extractor.extract("The rationale is that immutable data structures reduce bugs.")
        types = [r.type for r in records]
        assert ExpertiseType.DECISION in types


class TestBoundarySignals:
    def test_must_not_triggers_boundary(self, extractor: HeuristicExtractor) -> None:
        records = extractor.extract("Code must not write directly to the production database.")
        types = [r.type for r in records]
        assert ExpertiseType.BOUNDARY in types

    def test_hard_requirement_triggers_boundary(self, extractor: HeuristicExtractor) -> None:
        records = extractor.extract("It is a hard requirement that all API calls use TLS.")
        types = [r.type for r in records]
        assert ExpertiseType.BOUNDARY in types

    def test_non_negotiable_triggers_boundary(self, extractor: HeuristicExtractor) -> None:
        records = extractor.extract("Two-factor auth is non-negotiable for admin accounts.")
        types = [r.type for r in records]
        assert ExpertiseType.BOUNDARY in types


class TestInsightSignals:
    def test_interesting_finding_triggers_insight(self, extractor: HeuristicExtractor) -> None:
        records = extractor.extract("An interesting finding is that batching reduces latency by 40%.")
        types = [r.type for r in records]
        assert ExpertiseType.INSIGHT in types

    def test_i_noticed_that_triggers_insight(self, extractor: HeuristicExtractor) -> None:
        records = extractor.extract("I noticed that caching reduces DB load significantly.")
        types = [r.type for r in records]
        assert ExpertiseType.INSIGHT in types

    def test_worth_noting_triggers_insight(self, extractor: HeuristicExtractor) -> None:
        records = extractor.extract("Worth noting that this only applies to async routes.")
        types = [r.type for r in records]
        assert ExpertiseType.INSIGHT in types

    def test_observation_triggers_insight(self, extractor: HeuristicExtractor) -> None:
        records = extractor.extract("My observation after profiling is that I/O is the bottleneck.")
        types = [r.type for r in records]
        assert ExpertiseType.INSIGHT in types


class TestConfidenceRange:
    def test_all_records_have_confidence_in_range(self, extractor: HeuristicExtractor) -> None:
        text = (
            "Always use dependency injection. "
            "The fix was to add proper error handling. "
            "We decided to use Redis for caching. "
            "It is a hard requirement to log all errors. "
            "Worth noting that async is faster here."
        )
        records = extractor.extract(text)
        assert records, "Expected at least one record"
        for rec in records:
            assert 0.3 <= rec.confidence <= 0.5, (
                f"Confidence {rec.confidence} out of range for record: {rec.content!r}"
            )


class TestSourceAgent:
    def test_source_agent_is_heuristic_extractor(self, extractor: HeuristicExtractor) -> None:
        records = extractor.extract("Always use meaningful variable names in all code.")
        assert records
        for rec in records:
            assert rec.source_agent == "heuristic-extractor"


class TestDeduplication:
    def test_same_sentence_not_duplicated(self, extractor: HeuristicExtractor) -> None:
        # Two signals in the same sentence should produce one record for that sentence
        text = "Always use type annotations because it is a hard requirement for our codebase."
        records = extractor.extract(text)
        contents = [r.content for r in records]
        # No content should appear more than once
        assert len(contents) == len(set(c[:100].lower() for c in contents))

    def test_distinct_sentences_not_deduplicated(self, extractor: HeuristicExtractor) -> None:
        text = (
            "Always use type annotations in new code.\n\n"
            "Always use black formatter before committing."
        )
        records = extractor.extract(text)
        assert len(records) >= 2


class TestContentLength:
    def test_extracted_content_at_least_10_chars(self, extractor: HeuristicExtractor) -> None:
        records = extractor.extract("We decided to use async everywhere in this project.")
        for rec in records:
            assert len(rec.content) >= 10, f"Content too short: {rec.content!r}"


class TestDomainAndProject:
    def test_domain_passed_through(self, extractor: HeuristicExtractor) -> None:
        records = extractor.extract(
            "Always use dependency injection.",
            domain="backend",
        )
        assert records
        for rec in records:
            assert rec.domain == "backend"

    def test_project_passed_through(self, extractor: HeuristicExtractor) -> None:
        records = extractor.extract(
            "Always use dependency injection.",
            project="my-service",
        )
        assert records
        for rec in records:
            assert rec.project == "my-service"

    def test_domain_defaults_to_general(self, extractor: HeuristicExtractor) -> None:
        records = extractor.extract("Always use dependency injection.")
        assert records
        for rec in records:
            assert rec.domain == "general"

    def test_project_defaults_to_none(self, extractor: HeuristicExtractor) -> None:
        records = extractor.extract("Always use dependency injection.")
        assert records
        for rec in records:
            assert rec.project is None


class TestSentenceExtraction:
    def test_extracted_content_contains_full_sentence(self, extractor: HeuristicExtractor) -> None:
        text = "We had a performance problem. The fix was to add a composite index on (user_id, created_at). This resolved the issue."
        records = extractor.extract(text)
        failure_records = [r for r in records if r.type == ExpertiseType.FAILURE]
        assert failure_records
        # Should contain the full sentence, not just "The fix was"
        content = failure_records[0].content
        assert "composite index" in content or "user_id" in content

    def test_extracted_content_is_not_just_trigger(self, extractor: HeuristicExtractor) -> None:
        text = "Always use the async pattern when dealing with I/O-bound operations in Python."
        records = extractor.extract(text)
        assert records
        # Content must be more than just the trigger phrase
        for rec in records:
            assert len(rec.content) > len("Always use")


class TestSeverityAssignment:
    def test_failure_records_have_severity(self, extractor: HeuristicExtractor) -> None:
        records = extractor.extract("The root cause was a missing null check in the parser.")
        failure_records = [r for r in records if r.type == ExpertiseType.FAILURE]
        assert failure_records
        for rec in failure_records:
            assert rec.severity == ExpertiseSeverity.MEDIUM

    def test_boundary_records_have_severity(self, extractor: HeuristicExtractor) -> None:
        records = extractor.extract("It is a hard requirement to encrypt all PII at rest.")
        boundary_records = [r for r in records if r.type == ExpertiseType.BOUNDARY]
        assert boundary_records
        for rec in boundary_records:
            assert rec.severity == ExpertiseSeverity.MEDIUM

    def test_convention_records_have_no_severity(self, extractor: HeuristicExtractor) -> None:
        records = extractor.extract("Always use meaningful commit messages in git history.")
        convention_records = [r for r in records if r.type == ExpertiseType.CONVENTION]
        assert convention_records
        for rec in convention_records:
            assert rec.severity is None
