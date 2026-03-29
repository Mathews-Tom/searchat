"""Tests for the conversation filter."""
from __future__ import annotations

from datetime import datetime

import pytest

from searchat.core.conversation_filter import ConversationFilter
from searchat.models.domain import SearchResult


def _make_result(
    title: str = "Normal conversation",
    message_count: int = 10,
) -> SearchResult:
    return SearchResult(
        conversation_id="abc",
        project_id="proj",
        title=title,
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 1, 1),
        message_count=message_count,
        file_path="/path.jsonl",
        score=1.0,
        snippet="snippet",
    )


class TestConversationFilter:
    @pytest.fixture()
    def cf(self) -> ConversationFilter:
        return ConversationFilter()

    def test_keeps_normal_conversations(self, cf: ConversationFilter) -> None:
        results = [_make_result()]
        filtered = cf.filter(results)
        assert len(filtered) == 1

    def test_removes_low_message_count(self, cf: ConversationFilter) -> None:
        results = [_make_result(message_count=1)]
        filtered = cf.filter(results)
        assert len(filtered) == 0

    def test_removes_automated_title_prefix(self, cf: ConversationFilter) -> None:
        for title in ["auto deploy", "Bot check", "CI run #42", "System alert"]:
            results = [_make_result(title=title)]
            filtered = cf.filter(results)
            assert len(filtered) == 0, f"Expected '{title}' to be filtered"

    def test_removes_auto_generated_keyword(self, cf: ConversationFilter) -> None:
        results = [_make_result(title="This is auto-generated content")]
        filtered = cf.filter(results)
        assert len(filtered) == 0

    def test_preserves_order(self, cf: ConversationFilter) -> None:
        results = [
            _make_result(title="First"),
            _make_result(title="Second"),
            _make_result(title="Third"),
        ]
        filtered = cf.filter(results)
        assert [r.title for r in filtered] == ["First", "Second", "Third"]

    def test_disable_automated_filter(self) -> None:
        cf = ConversationFilter(exclude_automated=False)
        results = [_make_result(title="auto deploy")]
        filtered = cf.filter(results)
        assert len(filtered) == 1

    def test_custom_min_message_count(self) -> None:
        cf = ConversationFilter(min_message_count=5)
        results = [_make_result(message_count=4)]
        filtered = cf.filter(results)
        assert len(filtered) == 0
