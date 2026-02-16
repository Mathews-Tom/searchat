from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

import pytest

# Mock the circular import before importing chat_service
sys.modules["searchat.api.dependencies"] = MagicMock()

from searchat.models import SearchResult, SearchResults
from searchat.services import chat_service
from searchat.services.chat_service import (
    ChatSession,
    get_or_create_session,
    generate_answer_stream,
    generate_rag_response,
)


@pytest.fixture(autouse=True)
def clear_sessions():
    """Clear session cache before and after each test."""
    chat_service._sessions.clear()
    yield
    chat_service._sessions.clear()


def _make_results(count: int) -> list[SearchResult]:
    """Create mock search results."""
    now = datetime.now()
    results: list[SearchResult] = []
    for idx in range(count):
        results.append(
            SearchResult(
                conversation_id=f"conv-{idx}",
                project_id="project-1",
                title=f"Title {idx}",
                created_at=now - timedelta(days=10),
                updated_at=now - timedelta(days=1),
                message_count=5,
                file_path=f"/path/conv-{idx}.jsonl",
                score=1.0 - (idx / 100.0),
                snippet=f"Snippet {idx} content",
                message_start_index=0,
                message_end_index=3,
            )
        )
    return results


class TestChatSession:
    """Test ChatSession dataclass."""

    def test_chat_session_creation(self):
        """Test creating a ChatSession instance."""
        session = ChatSession(
            session_id="test-123",
            messages=[],
            created_at=123.0,
            last_active=123.0,
        )
        assert session.session_id == "test-123"
        assert session.messages == []
        assert session.created_at == 123.0
        assert session.last_active == 123.0

    def test_chat_session_with_messages(self):
        """Test ChatSession with message history."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        session = ChatSession(
            session_id="test-456",
            messages=messages,
            created_at=100.0,
            last_active=200.0,
        )
        assert len(session.messages) == 2
        assert session.messages[0]["role"] == "user"
        assert session.messages[1]["content"] == "Hi there"


class TestGetOrCreateSession:
    """Test session retrieval and creation logic."""

    def test_create_new_session_when_none_exists(self):
        """Test creating a new session when session_id is None."""
        session = get_or_create_session(None)
        assert session.session_id is not None
        assert len(session.session_id) == 16
        assert session.messages == []
        assert session.session_id in chat_service._sessions

    def test_create_new_session_when_id_not_found(self):
        """Test creating a new session when given ID doesn't exist."""
        session = get_or_create_session("nonexistent-id")
        assert session.session_id != "nonexistent-id"
        assert len(session.session_id) == 16
        assert session.messages == []

    def test_retrieve_existing_session(self):
        """Test retrieving an existing session by ID."""
        first_session = get_or_create_session(None)
        first_id = first_session.session_id
        first_session.messages.append({"role": "user", "content": "test"})

        second_session = get_or_create_session(first_id)
        assert second_session.session_id == first_id
        assert len(second_session.messages) == 1
        assert second_session.messages[0]["content"] == "test"

    def test_retrieve_updates_last_active(self):
        """Test that retrieving a session updates last_active timestamp."""
        session1 = get_or_create_session(None)
        initial_time = session1.last_active
        time.sleep(0.01)

        session2 = get_or_create_session(session1.session_id)
        assert session2.last_active > initial_time

    def test_multiple_sessions_coexist(self):
        """Test that multiple sessions can exist simultaneously."""
        session1 = get_or_create_session(None)
        session2 = get_or_create_session(None)
        assert session1.session_id != session2.session_id
        assert len(chat_service._sessions) == 2


class TestSessionEviction:
    """Test session expiration and eviction logic."""

    def test_evict_expired_removes_old_sessions(self):
        """Test that expired sessions are removed."""
        session = get_or_create_session(None)
        session_id = session.session_id

        # Manually set last_active to expired time
        session.last_active = time.time() - (chat_service._SESSION_TTL + 100)

        chat_service._evict_expired()
        assert session_id not in chat_service._sessions

    def test_evict_expired_keeps_active_sessions(self):
        """Test that active sessions are not removed."""
        session = get_or_create_session(None)
        session_id = session.session_id

        # Session is active (recent last_active)
        session.last_active = time.time()

        chat_service._evict_expired()
        assert session_id in chat_service._sessions

    def test_evict_expired_with_multiple_sessions(self):
        """Test eviction with mix of active and expired sessions."""
        active_session = get_or_create_session(None)
        expired_session = get_or_create_session(None)

        active_session.last_active = time.time()
        expired_session.last_active = time.time() - (chat_service._SESSION_TTL + 100)

        chat_service._evict_expired()
        assert active_session.session_id in chat_service._sessions
        assert expired_session.session_id not in chat_service._sessions

    def test_evict_expired_called_on_get_or_create(self):
        """Test that eviction happens automatically on session access."""
        expired_session = get_or_create_session(None)
        expired_session.last_active = time.time() - (chat_service._SESSION_TTL + 100)
        expired_id = expired_session.session_id

        # Creating a new session should trigger eviction
        new_session = get_or_create_session(None)
        assert expired_id not in chat_service._sessions
        assert new_session.session_id in chat_service._sessions


class TestGenerateAnswerStreamWithSessions:
    """Test streaming generation with session management."""

    def test_generate_answer_stream_creates_session(self):
        """Test that generate_answer_stream creates a session."""
        mock_engine = Mock()
        mock_engine.search.return_value = SearchResults(
            results=_make_results(5),
            total_count=5,
            search_time_ms=5.0,
            mode_used="hybrid",
        )
        config = Mock()
        config.llm = object()

        with patch("searchat.services.chat_service.get_search_engine", return_value=mock_engine):
            with patch("searchat.services.chat_service.LLMService.stream_completion") as mock_stream:
                mock_stream.return_value = iter(["Hello", " ", "world"])

                session_id, stream = generate_answer_stream(
                    query="test query",
                    provider="ollama",
                    model_name=None,
                    config=config,
                    session_id=None,
                )

                # Consume stream
                list(stream)

        assert session_id is not None
        assert session_id in chat_service._sessions

    def test_generate_answer_stream_uses_existing_session(self):
        """Test that generate_answer_stream reuses an existing session."""
        existing_session = get_or_create_session(None)
        existing_id = existing_session.session_id
        existing_session.messages.append({"role": "user", "content": "previous"})
        existing_session.messages.append({"role": "assistant", "content": "answer"})

        mock_engine = Mock()
        mock_engine.search.return_value = SearchResults(
            results=_make_results(5),
            total_count=5,
            search_time_ms=5.0,
            mode_used="hybrid",
        )
        config = Mock()
        config.llm = object()

        with patch("searchat.services.chat_service.get_search_engine", return_value=mock_engine):
            with patch("searchat.services.chat_service.LLMService.stream_completion") as mock_stream:
                mock_stream.return_value = iter(["new", " ", "response"])

                session_id, stream = generate_answer_stream(
                    query="new query",
                    provider="ollama",
                    model_name=None,
                    config=config,
                    session_id=existing_id,
                )

                # Consume stream
                list(stream)

        assert session_id == existing_id
        session = chat_service._sessions[existing_id]
        assert len(session.messages) == 4  # 2 old + 2 new

    def test_generate_answer_stream_updates_session_history(self):
        """Test that streaming updates session with query and answer."""
        mock_engine = Mock()
        mock_engine.search.return_value = SearchResults(
            results=_make_results(5),
            total_count=5,
            search_time_ms=5.0,
            mode_used="hybrid",
        )
        config = Mock()
        config.llm = object()

        with patch("searchat.services.chat_service.get_search_engine", return_value=mock_engine):
            with patch("searchat.services.chat_service.LLMService.stream_completion") as mock_stream:
                mock_stream.return_value = iter(["Test", " ", "answer"])

                session_id, stream = generate_answer_stream(
                    query="What is the answer?",
                    provider="ollama",
                    model_name=None,
                    config=config,
                )

                # Consume stream
                list(stream)

        session = chat_service._sessions[session_id]
        assert len(session.messages) == 2
        assert session.messages[0] == {"role": "user", "content": "What is the answer?"}
        assert session.messages[1] == {"role": "assistant", "content": "Test answer"}

    def test_generate_answer_stream_with_no_results(self):
        """Test streaming when no search results found."""
        mock_engine = Mock()
        mock_engine.search.return_value = SearchResults(
            results=[],
            total_count=0,
            search_time_ms=1.0,
            mode_used="hybrid",
        )
        config = Mock()
        config.llm = object()

        with patch("searchat.services.chat_service.get_search_engine", return_value=mock_engine):
            session_id, stream = generate_answer_stream(
                query="unknown query",
                provider="ollama",
                model_name=None,
                config=config,
            )

            response = "".join(stream)

        assert response == "I cannot find the information in the archives."
        session = chat_service._sessions[session_id]
        assert len(session.messages) == 2
        assert session.messages[1]["content"] == "I cannot find the information in the archives."

    def test_generate_answer_stream_applies_sliding_window(self):
        """Test that only last MAX_TURNS messages are used in context."""
        session = get_or_create_session(None)
        session_id = session.session_id

        # Add more than MAX_TURNS worth of messages
        for i in range(chat_service._MAX_TURNS * 2 + 5):
            session.messages.append({"role": "user", "content": f"msg {i}"})
            session.messages.append({"role": "assistant", "content": f"reply {i}"})

        mock_engine = Mock()
        mock_engine.search.return_value = SearchResults(
            results=_make_results(5),
            total_count=5,
            search_time_ms=5.0,
            mode_used="hybrid",
        )
        config = Mock()
        config.llm = object()

        with patch("searchat.services.chat_service.get_search_engine", return_value=mock_engine):
            with patch("searchat.services.chat_service.LLMService.stream_completion") as mock_stream:
                mock_stream.return_value = iter(["ok"])

                _, stream = generate_answer_stream(
                    query="test",
                    provider="ollama",
                    model_name=None,
                    config=config,
                    session_id=session_id,
                )

                list(stream)

                # Check that LLM was called with limited history
                call_args = mock_stream.call_args
                messages = call_args[1]["messages"]

                # Should have: system + history (max MAX_TURNS*2) + current user message
                # History should be last MAX_TURNS*2 messages
                history_messages = [m for m in messages if m["role"] != "system"]
                # Remove the last user message (current query)
                history_without_current = history_messages[:-1]
                assert len(history_without_current) <= chat_service._MAX_TURNS * 2


class TestGenerateRAGResponseWithSessions:
    """Test non-streaming RAG generation with session management."""

    def test_generate_rag_response_creates_session(self):
        """Test that generate_rag_response creates a session."""
        mock_engine = Mock()
        mock_engine.search.return_value = SearchResults(
            results=_make_results(8),
            total_count=8,
            search_time_ms=5.0,
            mode_used="hybrid",
        )
        config = Mock()
        config.llm = object()

        with patch("searchat.services.chat_service.get_search_engine", return_value=mock_engine):
            with patch("searchat.services.chat_service.LLMService.completion", return_value="Answer text"):
                result = generate_rag_response(
                    query="test query",
                    provider="ollama",
                    model_name=None,
                    config=config,
                )

        assert result.session_id is not None
        assert result.session_id in chat_service._sessions

    def test_generate_rag_response_uses_existing_session(self):
        """Test that generate_rag_response reuses existing session."""
        existing_session = get_or_create_session(None)
        existing_id = existing_session.session_id
        existing_session.messages.append({"role": "user", "content": "previous"})
        existing_session.messages.append({"role": "assistant", "content": "answer"})

        mock_engine = Mock()
        mock_engine.search.return_value = SearchResults(
            results=_make_results(8),
            total_count=8,
            search_time_ms=5.0,
            mode_used="hybrid",
        )
        config = Mock()
        config.llm = object()

        with patch("searchat.services.chat_service.get_search_engine", return_value=mock_engine):
            with patch("searchat.services.chat_service.LLMService.completion", return_value="New answer"):
                result = generate_rag_response(
                    query="new query",
                    provider="ollama",
                    model_name=None,
                    config=config,
                    session_id=existing_id,
                )

        assert result.session_id == existing_id
        session = chat_service._sessions[existing_id]
        assert len(session.messages) == 4

    def test_generate_rag_response_updates_session_history(self):
        """Test that RAG generation updates session history."""
        mock_engine = Mock()
        mock_engine.search.return_value = SearchResults(
            results=_make_results(8),
            total_count=8,
            search_time_ms=5.0,
            mode_used="hybrid",
        )
        config = Mock()
        config.llm = object()

        with patch("searchat.services.chat_service.get_search_engine", return_value=mock_engine):
            with patch("searchat.services.chat_service.LLMService.completion", return_value="Complete answer"):
                result = generate_rag_response(
                    query="What is the question?",
                    provider="ollama",
                    model_name=None,
                    config=config,
                )

        session = chat_service._sessions[result.session_id]
        assert len(session.messages) == 2
        assert session.messages[0] == {"role": "user", "content": "What is the question?"}
        assert session.messages[1] == {"role": "assistant", "content": "Complete answer"}

    def test_generate_rag_response_with_no_results(self):
        """Test RAG generation when no search results found."""
        mock_engine = Mock()
        mock_engine.search.return_value = SearchResults(
            results=[],
            total_count=0,
            search_time_ms=1.0,
            mode_used="hybrid",
        )
        config = Mock()
        config.llm = object()

        with patch("searchat.services.chat_service.get_search_engine", return_value=mock_engine):
            result = generate_rag_response(
                query="unknown query",
                provider="ollama",
                model_name=None,
                config=config,
            )

        assert result.answer == "I cannot find the information in the archives."
        assert result.context_used == 0
        assert len(result.results) == 0
        # Session should still be created, but no messages added
        assert result.session_id in chat_service._sessions

    def test_generate_rag_response_applies_sliding_window(self):
        """Test that only last MAX_TURNS messages are used."""
        session = get_or_create_session(None)
        session_id = session.session_id

        # Add more than MAX_TURNS worth of messages
        for i in range(chat_service._MAX_TURNS * 2 + 5):
            session.messages.append({"role": "user", "content": f"msg {i}"})
            session.messages.append({"role": "assistant", "content": f"reply {i}"})

        mock_engine = Mock()
        mock_engine.search.return_value = SearchResults(
            results=_make_results(8),
            total_count=8,
            search_time_ms=5.0,
            mode_used="hybrid",
        )
        config = Mock()
        config.llm = object()

        with patch("searchat.services.chat_service.get_search_engine", return_value=mock_engine):
            with patch("searchat.services.chat_service.LLMService.completion", return_value="ok") as mock_completion:
                generate_rag_response(
                    query="test",
                    provider="ollama",
                    model_name=None,
                    config=config,
                    session_id=session_id,
                )

                call_args = mock_completion.call_args
                messages = call_args[1]["messages"]

                # Should have: system + history (max MAX_TURNS*2) + current user message
                history_messages = [m for m in messages if m["role"] != "system"]
                history_without_current = history_messages[:-1]
                assert len(history_without_current) <= chat_service._MAX_TURNS * 2

    def test_multiple_turns_in_same_session(self):
        """Test multiple query/response turns in same session."""
        mock_engine = Mock()
        mock_engine.search.return_value = SearchResults(
            results=_make_results(8),
            total_count=8,
            search_time_ms=5.0,
            mode_used="hybrid",
        )
        config = Mock()
        config.llm = object()

        session_id = None
        queries = ["First question", "Second question", "Third question"]

        with patch("searchat.services.chat_service.get_search_engine", return_value=mock_engine):
            with patch("searchat.services.chat_service.LLMService.completion") as mock_completion:
                mock_completion.side_effect = ["Answer 1", "Answer 2", "Answer 3"]

                for query in queries:
                    result = generate_rag_response(
                        query=query,
                        provider="ollama",
                        model_name=None,
                        config=config,
                        session_id=session_id,
                    )
                    session_id = result.session_id

        session = chat_service._sessions[session_id]
        assert len(session.messages) == 6  # 3 turns * 2 messages
        assert session.messages[0]["content"] == "First question"
        assert session.messages[1]["content"] == "Answer 1"
        assert session.messages[4]["content"] == "Third question"
        assert session.messages[5]["content"] == "Answer 3"
