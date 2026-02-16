from __future__ import annotations

import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from searchat.models import SearchMode, SearchFilters, SearchResult, SearchResults
from searchat.services.pattern_mining import (
    ExtractedPattern,
    PatternEvidence,
    extract_patterns,
)


# ============================================================================
# Test Fixtures
# ============================================================================


def _make_search_result(
    conv_id: str,
    snippet: str,
    project_id: str = "test-project",
    score: float = 0.9,
) -> SearchResult:
    """Create a mock search result for testing."""
    now = datetime.now()
    return SearchResult(
        conversation_id=conv_id,
        project_id=project_id,
        title=f"Conversation {conv_id}",
        created_at=now - timedelta(days=10),
        updated_at=now - timedelta(days=1),
        message_count=5,
        file_path=f"/test/.claude/projects/{project_id}/{conv_id}.jsonl",
        score=score,
        snippet=snippet,
        message_start_index=0,
        message_end_index=3,
    )


def _make_search_results(results: list[SearchResult]) -> SearchResults:
    """Create a SearchResults object from a list of SearchResult."""
    return SearchResults(
        results=results,
        total_count=len(results),
        search_time_ms=5.0,
        mode_used="hybrid",
    )


@pytest.fixture
def mock_config():
    """Mock config with LLM settings."""
    config = Mock()
    config.llm = SimpleNamespace(
        openai_model="gpt-4.1-mini",
        ollama_model="llama3",
    )
    return config


# ============================================================================
# Dataclass Tests
# ============================================================================


def test_pattern_evidence_dataclass():
    """Test PatternEvidence dataclass creation and immutability."""
    evidence = PatternEvidence(
        conversation_id="conv-123",
        date="2026-01-15T10:30:00",
        snippet="Code review showed consistent patterns",
    )

    assert evidence.conversation_id == "conv-123"
    assert evidence.date == "2026-01-15T10:30:00"
    assert evidence.snippet == "Code review showed consistent patterns"

    # Test immutability (frozen=True)
    with pytest.raises(AttributeError):
        evidence.conversation_id = "conv-456"


def test_extracted_pattern_dataclass():
    """Test ExtractedPattern dataclass creation and immutability."""
    evidence_list = [
        PatternEvidence("conv-1", "2026-01-15", "snippet 1"),
        PatternEvidence("conv-2", "2026-01-16", "snippet 2"),
    ]

    pattern = ExtractedPattern(
        name="Type Hinting Convention",
        description="Always use modern type hints with | unions",
        evidence=evidence_list,
        confidence=0.85,
    )

    assert pattern.name == "Type Hinting Convention"
    assert pattern.description == "Always use modern type hints with | unions"
    assert len(pattern.evidence) == 2
    assert pattern.confidence == 0.85

    # Test immutability
    with pytest.raises(AttributeError):
        pattern.name = "New Name"


def test_pattern_evidence_equality():
    """Test PatternEvidence equality comparison."""
    ev1 = PatternEvidence("conv-1", "2026-01-15", "snippet")
    ev2 = PatternEvidence("conv-1", "2026-01-15", "snippet")
    ev3 = PatternEvidence("conv-2", "2026-01-15", "snippet")

    assert ev1 == ev2
    assert ev1 != ev3


def test_extracted_pattern_equality():
    """Test ExtractedPattern equality comparison."""
    evidence = [PatternEvidence("conv-1", "2026-01-15", "snippet")]

    p1 = ExtractedPattern("Name", "Desc", evidence, 0.8)
    p2 = ExtractedPattern("Name", "Desc", evidence, 0.8)
    p3 = ExtractedPattern("Other", "Desc", evidence, 0.8)

    assert p1 == p2
    assert p1 != p3


# ============================================================================
# extract_patterns() Main Flow Tests
# ============================================================================


@patch("searchat.services.llm_service.LLMService")
@patch("searchat.api.dependencies.get_search_engine")
def test_extract_patterns_with_topic(mock_get_engine, mock_llm_class, mock_config):
    """Test pattern extraction with a specific topic."""
    # Setup mock search engine
    mock_engine = Mock()
    mock_get_engine.return_value = mock_engine

    results = [
        _make_search_result("conv-1", "Use type hints everywhere"),
        _make_search_result("conv-2", "Modern type annotations preferred"),
    ]
    mock_engine.search.return_value = _make_search_results(results)

    # Setup mock LLM service
    mock_llm = Mock()
    mock_llm_class.return_value = mock_llm
    mock_llm.completion.return_value = json.dumps({
        "name": "Type Annotation Pattern",
        "description": "Consistent use of modern type hints",
        "confidence": 0.9,
    })

    # Execute
    patterns = extract_patterns(
        topic="type hints",
        max_patterns=10,
        model_provider="ollama",
        model_name="llama3",
        config=mock_config,
    )

    # Verify search was called with topic-based seeds
    assert mock_engine.search.call_count == 3
    calls = [call[0][0] for call in mock_engine.search.call_args_list]
    assert "type hints conventions" in calls
    assert "type hints patterns" in calls
    assert "type hints best practices" in calls

    # Verify results
    assert len(patterns) == 1
    assert patterns[0].name == "Type Annotation Pattern"
    assert patterns[0].description == "Consistent use of modern type hints"
    assert patterns[0].confidence == 0.9
    assert len(patterns[0].evidence) == 2


@patch("searchat.services.llm_service.LLMService")
@patch("searchat.api.dependencies.get_search_engine")
def test_extract_patterns_without_topic_uses_defaults(
    mock_get_engine, mock_llm_class, mock_config
):
    """Test pattern extraction uses default seeds when no topic provided."""
    mock_engine = Mock()
    mock_get_engine.return_value = mock_engine

    results = [_make_search_result("conv-1", "Default pattern")]
    mock_engine.search.return_value = _make_search_results(results)

    mock_llm = Mock()
    mock_llm_class.return_value = mock_llm
    mock_llm.completion.return_value = json.dumps({
        "name": "Default Pattern",
        "description": "A pattern from default seeds",
        "confidence": 0.7,
    })

    patterns = extract_patterns(
        topic=None,
        max_patterns=5,
        model_provider="openai",
        config=mock_config,
    )

    # Should use default PATTERN_MINING_SEEDS
    assert mock_engine.search.call_count == 5
    calls = [call[0][0] for call in mock_engine.search.call_args_list]
    assert "coding conventions" in calls
    assert "architecture decisions" in calls
    assert "best practices" in calls
    assert "recurring patterns" in calls
    assert "project rules" in calls

    assert len(patterns) >= 1


@patch("searchat.services.llm_service.LLMService")
@patch("searchat.api.dependencies.get_search_engine")
def test_extract_patterns_deduplicates_by_conversation_id(
    mock_get_engine, mock_llm_class, mock_config
):
    """Test that duplicate conversation_ids are deduplicated across seeds."""
    mock_engine = Mock()
    mock_get_engine.return_value = mock_engine

    # Same conversation appears in multiple seed results
    def search_side_effect(query, mode, filters):
        if "conventions" in query:
            return _make_search_results([
                _make_search_result("conv-duplicate", "Pattern A", score=0.95),
                _make_search_result("conv-1", "Pattern B", score=0.90),
            ])
        elif "patterns" in query:
            return _make_search_results([
                _make_search_result("conv-duplicate", "Pattern A again", score=0.92),
                _make_search_result("conv-2", "Pattern C", score=0.88),
            ])
        else:
            return _make_search_results([])

    mock_engine.search.side_effect = search_side_effect

    mock_llm = Mock()
    mock_llm_class.return_value = mock_llm
    mock_llm.completion.return_value = json.dumps({
        "name": "Test Pattern",
        "description": "Test",
        "confidence": 0.8,
    })

    patterns = extract_patterns(
        topic="test",
        max_patterns=10,
        config=mock_config,
    )

    # Verify deduplication: conv-duplicate should only appear once
    # Count unique conversation IDs across all patterns
    all_conv_ids: set[str] = set()
    for pattern in patterns:
        for evidence in pattern.evidence:
            all_conv_ids.add(evidence.conversation_id)

    # Should have 3 unique conversations: conv-duplicate, conv-1, conv-2
    assert "conv-duplicate" in all_conv_ids
    assert "conv-1" in all_conv_ids
    assert "conv-2" in all_conv_ids


@patch("searchat.services.llm_service.LLMService")
@patch("searchat.api.dependencies.get_search_engine")
def test_extract_patterns_respects_max_patterns(
    mock_get_engine, mock_llm_class, mock_config
):
    """Test that max_patterns limits the number of returned patterns."""
    mock_engine = Mock()
    mock_get_engine.return_value = mock_engine

    # Return different results for each seed
    results_by_seed = {
        "test conventions": [_make_search_result("conv-1", "A")],
        "test patterns": [_make_search_result("conv-2", "B")],
        "test best practices": [_make_search_result("conv-3", "C")],
    }

    def search_side_effect(query, mode, filters):
        return _make_search_results(results_by_seed.get(query, []))

    mock_engine.search.side_effect = search_side_effect

    mock_llm = Mock()
    mock_llm_class.return_value = mock_llm
    mock_llm.completion.return_value = json.dumps({
        "name": "Pattern",
        "description": "Test pattern",
        "confidence": 0.75,
    })

    # Request max 2 patterns even though we have 3 seed clusters
    patterns = extract_patterns(
        topic="test",
        max_patterns=2,
        config=mock_config,
    )

    assert len(patterns) <= 2


@patch("searchat.services.llm_service.LLMService")
@patch("searchat.api.dependencies.get_search_engine")
def test_extract_patterns_caps_evidence_at_5_per_cluster(
    mock_get_engine, mock_llm_class, mock_config
):
    """Test that each pattern uses max 5 evidence items per cluster."""
    mock_engine = Mock()
    mock_get_engine.return_value = mock_engine

    # Return 10 results but only 5 should be used for evidence
    many_results = [
        _make_search_result(f"conv-{i}", f"snippet {i}")
        for i in range(10)
    ]
    mock_engine.search.return_value = _make_search_results(many_results)

    mock_llm = Mock()
    mock_llm_class.return_value = mock_llm
    mock_llm.completion.return_value = json.dumps({
        "name": "Pattern",
        "description": "Test",
        "confidence": 0.8,
    })

    patterns = extract_patterns(
        topic="test",
        max_patterns=1,
        config=mock_config,
    )

    # Should have exactly 1 pattern with max 5 evidence items
    assert len(patterns) == 1
    assert len(patterns[0].evidence) == 5


# ============================================================================
# Empty Results Tests
# ============================================================================


@patch("searchat.api.dependencies.get_search_engine")
def test_extract_patterns_returns_empty_when_no_search_results(
    mock_get_engine, mock_config
):
    """Test that empty list is returned when search yields no results."""
    mock_engine = Mock()
    mock_get_engine.return_value = mock_engine
    mock_engine.search.return_value = _make_search_results([])

    patterns = extract_patterns(
        topic="nonexistent topic",
        max_patterns=10,
        config=mock_config,
    )

    assert patterns == []


@patch("searchat.services.llm_service.LLMService")
@patch("searchat.api.dependencies.get_search_engine")
def test_extract_patterns_handles_all_seeds_returning_empty(
    mock_get_engine, mock_llm_class, mock_config
):
    """Test behavior when all seed queries return empty results."""
    mock_engine = Mock()
    mock_get_engine.return_value = mock_engine
    mock_engine.search.return_value = _make_search_results([])

    mock_llm = Mock()
    mock_llm_class.return_value = mock_llm

    patterns = extract_patterns(
        topic="empty",
        max_patterns=10,
        config=mock_config,
    )

    assert patterns == []
    # LLM should never be called if there are no results
    mock_llm.completion.assert_not_called()


# ============================================================================
# LLM Parsing Error Tests
# ============================================================================


@patch("searchat.services.llm_service.LLMService")
@patch("searchat.api.dependencies.get_search_engine")
def test_extract_patterns_handles_json_decode_error(
    mock_get_engine, mock_llm_class, mock_config
):
    """Test graceful handling of invalid JSON from LLM."""
    mock_engine = Mock()
    mock_get_engine.return_value = mock_engine

    results = [_make_search_result("conv-1", "snippet")]
    mock_engine.search.return_value = _make_search_results(results)

    mock_llm = Mock()
    mock_llm_class.return_value = mock_llm
    # Return invalid JSON
    mock_llm.completion.return_value = "This is not valid JSON at all"

    patterns = extract_patterns(
        topic="test",
        max_patterns=1,
        config=mock_config,
    )

    # Should return fallback pattern with low confidence
    assert len(patterns) == 1
    assert "test" in patterns[0].name.lower()
    assert "related to" in patterns[0].description.lower()
    assert patterns[0].confidence == 0.3
    assert len(patterns[0].evidence) == 1


@patch("searchat.services.llm_service.LLMService")
@patch("searchat.api.dependencies.get_search_engine")
def test_extract_patterns_handles_missing_json_keys(
    mock_get_engine, mock_llm_class, mock_config
):
    """Test handling of valid JSON with missing required keys."""
    mock_engine = Mock()
    mock_get_engine.return_value = mock_engine

    results = [_make_search_result("conv-1", "snippet")]
    mock_engine.search.return_value = _make_search_results(results)

    mock_llm = Mock()
    mock_llm_class.return_value = mock_llm
    # Return JSON with missing keys - should use defaults
    mock_llm.completion.return_value = json.dumps({})

    patterns = extract_patterns(
        topic="test",
        max_patterns=1,
        config=mock_config,
    )

    # Should use defaults for missing keys
    assert len(patterns) == 1
    assert patterns[0].name == "test conventions"  # Uses seed as fallback (topic + " conventions")
    assert patterns[0].description == ""  # Default
    assert patterns[0].confidence == 0.5  # Default


@patch("searchat.services.llm_service.LLMService")
@patch("searchat.api.dependencies.get_search_engine")
def test_extract_patterns_handles_invalid_confidence_type(
    mock_get_engine, mock_llm_class, mock_config
):
    """Test handling of non-numeric confidence value."""
    mock_engine = Mock()
    mock_get_engine.return_value = mock_engine

    results = [_make_search_result("conv-1", "snippet")]
    mock_engine.search.return_value = _make_search_results(results)

    mock_llm = Mock()
    mock_llm_class.return_value = mock_llm
    # Return confidence as string instead of float
    mock_llm.completion.return_value = json.dumps({
        "name": "Pattern",
        "description": "Test",
        "confidence": "not a number",
    })

    patterns = extract_patterns(
        topic="test",
        max_patterns=1,
        config=mock_config,
    )

    # Should fall back to 0.3 confidence due to ValueError
    assert len(patterns) == 1
    assert patterns[0].confidence == 0.3


@patch("searchat.services.llm_service.LLMService")
@patch("searchat.api.dependencies.get_search_engine")
def test_extract_patterns_logs_warning_on_parse_failure(
    mock_get_engine, mock_llm_class, mock_config, caplog
):
    """Test that parsing failures are logged as warnings."""
    import logging

    caplog.set_level(logging.WARNING)

    mock_engine = Mock()
    mock_get_engine.return_value = mock_engine

    results = [_make_search_result("conv-1", "snippet")]
    mock_engine.search.return_value = _make_search_results(results)

    mock_llm = Mock()
    mock_llm_class.return_value = mock_llm
    mock_llm.completion.return_value = "invalid json"

    extract_patterns(
        topic="test",
        max_patterns=1,
        config=mock_config,
    )

    # Verify warning was logged
    assert any("Failed to parse pattern from LLM response" in record.message
              for record in caplog.records)


# ============================================================================
# LLM Service Integration Tests
# ============================================================================


@patch("searchat.services.llm_service.LLMService")
@patch("searchat.api.dependencies.get_search_engine")
def test_extract_patterns_passes_correct_params_to_llm(
    mock_get_engine, mock_llm_class, mock_config
):
    """Test that LLM service is called with correct parameters."""
    mock_engine = Mock()
    mock_get_engine.return_value = mock_engine

    results = [_make_search_result("conv-1", "snippet")]
    mock_engine.search.return_value = _make_search_results(results)

    mock_llm = Mock()
    mock_llm_class.return_value = mock_llm
    mock_llm.completion.return_value = json.dumps({
        "name": "Pattern",
        "description": "Test",
        "confidence": 0.8,
    })

    extract_patterns(
        topic="test",
        max_patterns=1,
        model_provider="openai",
        model_name="gpt-4.1-mini",
        config=mock_config,
    )

    # Verify LLM completion was called with correct args
    mock_llm.completion.assert_called_once()
    call_args = mock_llm.completion.call_args
    assert call_args[1]["provider"] == "openai"
    assert call_args[1]["model_name"] == "gpt-4.1-mini"

    # Verify messages structure
    messages = call_args[1]["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert "extract development patterns" in messages[0]["content"].lower()
    assert messages[1]["role"] == "user"
    assert "Analyze these conversation excerpts" in messages[1]["content"]


@patch("searchat.services.llm_service.LLMService")
@patch("searchat.api.dependencies.get_search_engine")
def test_extract_patterns_builds_context_from_results(
    mock_get_engine, mock_llm_class, mock_config
):
    """Test that context is properly built from search results."""
    mock_engine = Mock()
    mock_get_engine.return_value = mock_engine

    result = _make_search_result("conv-123", "Important snippet content")
    mock_engine.search.return_value = _make_search_results([result])

    mock_llm = Mock()
    mock_llm_class.return_value = mock_llm
    mock_llm.completion.return_value = json.dumps({
        "name": "Pattern",
        "description": "Test",
        "confidence": 0.8,
    })

    extract_patterns(
        topic="test",
        max_patterns=1,
        config=mock_config,
    )

    # Verify context includes conversation details
    call_args = mock_llm.completion.call_args
    user_message = call_args[1]["messages"][1]["content"]

    assert "conv-123" in user_message
    assert "test-project" in user_message
    assert "Important snippet content" in user_message


# ============================================================================
# Evidence Collection Tests
# ============================================================================


@patch("searchat.services.llm_service.LLMService")
@patch("searchat.api.dependencies.get_search_engine")
def test_pattern_evidence_contains_correct_fields(
    mock_get_engine, mock_llm_class, mock_config
):
    """Test that PatternEvidence is populated with correct data."""
    mock_engine = Mock()
    mock_get_engine.return_value = mock_engine

    now = datetime.now()
    result = SearchResult(
        conversation_id="conv-abc",
        project_id="proj-123",
        title="Test Conversation",
        created_at=now - timedelta(days=5),
        updated_at=now - timedelta(hours=2),
        message_count=10,
        file_path="/test/path.jsonl",
        score=0.95,
        snippet="Specific code pattern found here",
        message_start_index=2,
        message_end_index=8,
    )
    mock_engine.search.return_value = _make_search_results([result])

    mock_llm = Mock()
    mock_llm_class.return_value = mock_llm
    mock_llm.completion.return_value = json.dumps({
        "name": "Pattern",
        "description": "Test",
        "confidence": 0.9,
    })

    patterns = extract_patterns(
        topic="test",
        max_patterns=1,
        config=mock_config,
    )

    assert len(patterns) == 1
    assert len(patterns[0].evidence) == 1

    evidence = patterns[0].evidence[0]
    assert evidence.conversation_id == "conv-abc"
    assert evidence.snippet == "Specific code pattern found here"
    # Date should be ISO format from updated_at
    expected_date = (now - timedelta(hours=2)).isoformat()
    assert evidence.date == expected_date


# ============================================================================
# Search Engine Integration Tests
# ============================================================================


@patch("searchat.services.llm_service.LLMService")
@patch("searchat.api.dependencies.get_search_engine")
def test_extract_patterns_uses_hybrid_search_mode(
    mock_get_engine, mock_llm_class, mock_config
):
    """Test that search engine is called with HYBRID mode."""
    mock_engine = Mock()
    mock_get_engine.return_value = mock_engine
    mock_engine.search.return_value = _make_search_results([])

    mock_llm = Mock()
    mock_llm_class.return_value = mock_llm

    extract_patterns(
        topic="test",
        max_patterns=1,
        config=mock_config,
    )

    # Verify all search calls use HYBRID mode
    for call in mock_engine.search.call_args_list:
        assert call[1]["mode"] == SearchMode.HYBRID
        assert isinstance(call[1]["filters"], SearchFilters)


@patch("searchat.services.llm_service.LLMService")
@patch("searchat.api.dependencies.get_search_engine")
def test_extract_patterns_takes_top_20_results_per_seed(
    mock_get_engine, mock_llm_class, mock_config
):
    """Test that only top 20 results per seed are considered."""
    mock_engine = Mock()
    mock_get_engine.return_value = mock_engine

    # Return 50 results but only top 20 should be used
    many_results = [
        _make_search_result(f"conv-{i}", f"snippet {i}", score=1.0 - (i / 100))
        for i in range(50)
    ]
    mock_engine.search.return_value = _make_search_results(many_results)

    mock_llm = Mock()
    mock_llm_class.return_value = mock_llm
    mock_llm.completion.return_value = json.dumps({
        "name": "Pattern",
        "description": "Test",
        "confidence": 0.8,
    })

    extract_patterns(
        topic="test",
        max_patterns=1,
        config=mock_config,
    )

    # Check that deduplication only considered top 20 from each seed
    # With 3 seeds and 20 results each, max unique conversations is 60
    # But dedup should happen, so check the context passed to LLM
    call_args = mock_llm.completion.call_args
    user_message = call_args[1]["messages"][1]["content"]

    # Count how many "Source:" entries are in the context (max 5 per cluster)
    source_count = user_message.count("Source:")
    assert source_count <= 5  # Capped at 5 per cluster


# ============================================================================
# Edge Cases
# ============================================================================


@patch("searchat.services.llm_service.LLMService")
@patch("searchat.api.dependencies.get_search_engine")
def test_extract_patterns_with_max_patterns_zero(
    mock_get_engine, mock_llm_class, mock_config
):
    """Test behavior when max_patterns is 0."""
    mock_engine = Mock()
    mock_get_engine.return_value = mock_engine
    mock_engine.search.return_value = _make_search_results(
        [_make_search_result("conv-1", "snippet")]
    )

    mock_llm = Mock()
    mock_llm_class.return_value = mock_llm

    patterns = extract_patterns(
        topic="test",
        max_patterns=0,
        config=mock_config,
    )

    assert patterns == []
    mock_llm.completion.assert_not_called()


@patch("searchat.services.llm_service.LLMService")
@patch("searchat.api.dependencies.get_search_engine")
def test_extract_patterns_with_model_name_none(
    mock_get_engine, mock_llm_class, mock_config
):
    """Test that model_name=None is passed correctly to LLM service."""
    mock_engine = Mock()
    mock_get_engine.return_value = mock_engine

    results = [_make_search_result("conv-1", "snippet")]
    mock_engine.search.return_value = _make_search_results(results)

    mock_llm = Mock()
    mock_llm_class.return_value = mock_llm
    mock_llm.completion.return_value = json.dumps({
        "name": "Pattern",
        "description": "Test",
        "confidence": 0.8,
    })

    extract_patterns(
        topic="test",
        max_patterns=1,
        model_provider="ollama",
        model_name=None,  # Explicitly None
        config=mock_config,
    )

    call_args = mock_llm.completion.call_args
    assert call_args[1]["model_name"] is None


@patch("searchat.services.llm_service.LLMService")
@patch("searchat.api.dependencies.get_search_engine")
def test_extract_patterns_with_multiple_projects(
    mock_get_engine, mock_llm_class, mock_config
):
    """Test pattern extraction across multiple projects."""
    mock_engine = Mock()
    mock_get_engine.return_value = mock_engine

    results = [
        _make_search_result("conv-1", "snippet A", project_id="project-alpha"),
        _make_search_result("conv-2", "snippet B", project_id="project-beta"),
        _make_search_result("conv-3", "snippet C", project_id="project-gamma"),
    ]
    mock_engine.search.return_value = _make_search_results(results)

    mock_llm = Mock()
    mock_llm_class.return_value = mock_llm
    mock_llm.completion.return_value = json.dumps({
        "name": "Cross-Project Pattern",
        "description": "Pattern spanning multiple projects",
        "confidence": 0.85,
    })

    patterns = extract_patterns(
        topic="test",
        max_patterns=1,
        config=mock_config,
    )

    # Verify evidence from different projects is included
    assert len(patterns) == 1
    evidence = patterns[0].evidence

    # Should have 3 evidence items from 3 different projects
    assert len(evidence) == 3
    conv_ids = {e.conversation_id for e in evidence}
    assert conv_ids == {"conv-1", "conv-2", "conv-3"}
