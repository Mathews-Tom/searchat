from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from searchat.models import SearchResult, SearchResults
from searchat.services.chat_service import generate_rag_response


def _make_results(count: int) -> list[SearchResult]:
    now = datetime.now()
    results: list[SearchResult] = []
    for idx in range(count):
        results.append(
            SearchResult(
                conversation_id=f"conv-{idx}",
                project_id="p",
                title=f"T {idx}",
                created_at=now - timedelta(days=10),
                updated_at=now - timedelta(days=1),
                message_count=5,
                file_path=f"/home/user/.claude/projects/p/conv-{idx}.jsonl",
                score=1.0 - (idx / 100.0),
                snippet=f"snippet {idx}",
                message_start_index=0,
                message_end_index=3,
            )
        )
    return results


def test_generate_rag_response_selects_more_context_for_complex_query():
    mock_engine = Mock()
    mock_engine.search.return_value = SearchResults(
        results=_make_results(30),
        total_count=30,
        search_time_ms=5.0,
        mode_used="hybrid",
    )

    config = Mock()
    config.llm = object()

    with patch("searchat.services.chat_service.get_search_engine", return_value=mock_engine):
        with patch("searchat.services.chat_service.LLMService.completion", return_value="ok"):
            simple = generate_rag_response(
                query="error parsing json",
                provider="ollama",
                model_name=None,
                config=config,
            )
            complex_ = generate_rag_response(
                query="Summarize and compare the approaches we discussed across sessions. Include tradeoffs and steps.",
                provider="ollama",
                model_name=None,
                config=config,
            )

    assert simple.context_used < complex_.context_used
    assert simple.context_used in (6, 8)
    assert complex_.context_used == 16
    assert len(simple.results) == simple.context_used
    assert len(complex_.results) == complex_.context_used
