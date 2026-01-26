"""Unit tests for conversations API routes."""
import pytest
import json
from datetime import datetime
from unittest.mock import Mock, patch, mock_open
from pathlib import Path

from fastapi.testclient import TestClient
from fastapi import HTTPException

from searchat.api.app import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_duckdb_store():
    """Mock DuckDBStore used by conversations routes."""
    mock = Mock()

    now = datetime.now()
    mock._data = [
        {
            "conversation_id": "conv-1",
            "project_id": "project-a",
            "title": "Python Binary Search",
            "created_at": now,
            "updated_at": now,
            "message_count": 10,
            "file_path": "/home/user/.claude/conv-1.jsonl",
            "full_text": "This is a conversation about implementing binary search in Python...",
        },
        {
            "conversation_id": "conv-2",
            "project_id": "project-b",
            "title": "API Design",
            "created_at": now,
            "updated_at": now,
            "message_count": 5,
            "file_path": "C:\\Users\\Test\\.claude\\conv-2.jsonl",
            "full_text": "Discussion about REST API design patterns",
        },
        {
            "conversation_id": "conv-3",
            "project_id": "project-a",
            "title": "Empty Conversation",
            "created_at": now,
            "updated_at": now,
            "message_count": 0,
            "file_path": "/home/user/.claude/conv-3.jsonl",
            "full_text": "",
        },
    ]

    def _list_conversations(*, sort_by="length", project_id=None, date_from=None, date_to=None):
        rows = [r for r in mock._data if r["message_count"] > 0]
        if project_id:
            rows = [r for r in rows if r["project_id"] == project_id]
        if date_from:
            rows = [r for r in rows if r["updated_at"] >= date_from]
        if date_to:
            rows = [r for r in rows if r["updated_at"] < date_to]

        if sort_by == "length":
            rows.sort(key=lambda r: r["message_count"], reverse=True)
        elif sort_by == "date_newest":
            rows.sort(key=lambda r: r["updated_at"], reverse=True)
        elif sort_by == "date_oldest":
            rows.sort(key=lambda r: r["updated_at"], reverse=False)
        elif sort_by == "title":
            rows.sort(key=lambda r: r["title"])

        return rows

    def _get_meta(conversation_id: str):
        for r in mock._data:
            if r["conversation_id"] == conversation_id:
                return {
                    "conversation_id": r["conversation_id"],
                    "project_id": r["project_id"],
                    "title": r["title"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                    "message_count": r["message_count"],
                    "file_path": r["file_path"],
                }
        return None

    mock.list_conversations.side_effect = _list_conversations
    mock.get_conversation_meta.side_effect = _get_meta
    return mock


@pytest.fixture
def mock_platform_manager():
    """Mock PlatformManager for terminal operations."""
    mock = Mock()
    mock.platform = "windows"
    mock.normalize_path = Mock(side_effect=lambda x: x)  # Return path unchanged
    mock.open_terminal_with_command = Mock()
    return mock


@pytest.mark.unit
class TestGetAllConversationsEndpoint:
    """Tests for GET /api/conversations/all endpoint."""

    def test_get_all_conversations_default_sort(self, client, mock_duckdb_store):
        """Test getting all conversations with default sort (by length)."""
        with patch('searchat.api.routers.conversations.deps.get_duckdb_store', return_value=mock_duckdb_store):
            response = client.get("/api/conversations/all")

            assert response.status_code == 200
            data = response.json()

            assert "results" in data
            assert "total" in data
            assert data["total"] == 2  # conv-3 filtered out (0 messages)

            # Should be sorted by message_count descending (conv-1: 10, conv-2: 5)
            assert data["results"][0]["conversation_id"] == "conv-1"
            assert data["results"][0]["message_count"] == 10
            assert data["results"][1]["conversation_id"] == "conv-2"
            assert data["results"][1]["message_count"] == 5

    def test_get_all_conversations_filters_zero_messages(self, client, mock_duckdb_store):
        """Test that conversations with 0 messages are filtered out."""
        with patch('searchat.api.routers.conversations.deps.get_duckdb_store', return_value=mock_duckdb_store):
            response = client.get("/api/conversations/all")

            assert response.status_code == 200
            data = response.json()

            # conv-3 has 0 messages and should be filtered
            conv_ids = [r["conversation_id"] for r in data["results"]]
            assert "conv-3" not in conv_ids
            assert len(data["results"]) == 2

    def test_get_all_conversations_sort_by_length(self, client, mock_duckdb_store):
        """Test sorting by message count (length)."""
        with patch('searchat.api.routers.conversations.deps.get_duckdb_store', return_value=mock_duckdb_store):
            response = client.get("/api/conversations/all?sort_by=length")

            assert response.status_code == 200
            data = response.json()

            # Descending order by message count
            assert data["results"][0]["message_count"] >= data["results"][1]["message_count"]

    def test_get_all_conversations_sort_by_date_newest(self, client, mock_duckdb_store):
        """Test sorting by newest date."""
        now = datetime.now()
        mock_duckdb_store._data = [
            {
                "conversation_id": "conv-old",
                "project_id": "project-a",
                "title": "Old",
                "created_at": now,
                "updated_at": datetime(2025, 1, 1),
                "message_count": 5,
                "file_path": "/test/old.jsonl",
                "full_text": "Old conversation",
            },
            {
                "conversation_id": "conv-new",
                "project_id": "project-a",
                "title": "New",
                "created_at": now,
                "updated_at": datetime(2025, 1, 31),
                "message_count": 5,
                "file_path": "/test/new.jsonl",
                "full_text": "New conversation",
            },
        ]

        with patch('searchat.api.routers.conversations.deps.get_duckdb_store', return_value=mock_duckdb_store):
            response = client.get("/api/conversations/all?sort_by=date_newest")

            assert response.status_code == 200
            data = response.json()

            # Newest first
            assert data["results"][0]["conversation_id"] == "conv-new"
            assert data["results"][1]["conversation_id"] == "conv-old"

    def test_get_all_conversations_sort_by_date_oldest(self, client, mock_duckdb_store):
        """Test sorting by oldest date."""
        now = datetime.now()
        mock_duckdb_store._data = [
            {
                "conversation_id": "conv-old",
                "project_id": "project-a",
                "title": "Old",
                "created_at": now,
                "updated_at": datetime(2025, 1, 1),
                "message_count": 5,
                "file_path": "/test/old.jsonl",
                "full_text": "Old conversation",
            },
            {
                "conversation_id": "conv-new",
                "project_id": "project-a",
                "title": "New",
                "created_at": now,
                "updated_at": datetime(2025, 1, 31),
                "message_count": 5,
                "file_path": "/test/new.jsonl",
                "full_text": "New conversation",
            },
        ]

        with patch('searchat.api.routers.conversations.deps.get_duckdb_store', return_value=mock_duckdb_store):
            response = client.get("/api/conversations/all?sort_by=date_oldest")

            assert response.status_code == 200
            data = response.json()

            # Oldest first
            assert data["results"][0]["conversation_id"] == "conv-old"
            assert data["results"][1]["conversation_id"] == "conv-new"

    def test_get_all_conversations_sort_by_title(self, client, mock_duckdb_store):
        """Test sorting by title alphabetically."""
        with patch('searchat.api.routers.conversations.deps.get_duckdb_store', return_value=mock_duckdb_store):
            response = client.get("/api/conversations/all?sort_by=title")

            assert response.status_code == 200
            data = response.json()

            # Alphabetical order
            titles = [r["title"] for r in data["results"]]
            assert titles == sorted(titles)

    def test_get_all_conversations_source_detection(self, client, mock_duckdb_store):
        """Test that source (WSL/WIN) is detected correctly."""
        with patch('searchat.api.routers.conversations.deps.get_duckdb_store', return_value=mock_duckdb_store):
            response = client.get("/api/conversations/all")

            assert response.status_code == 200
            data = response.json()

            # conv-1 has /home/ path (WSL)
            conv1 = next(r for r in data["results"] if r["conversation_id"] == "conv-1")
            assert conv1["source"] == "WSL"

            # conv-2 has C:\ path (Windows)
            conv2 = next(r for r in data["results"] if r["conversation_id"] == "conv-2")
            assert conv2["source"] == "WIN"

    def test_get_all_conversations_snippet_truncation(self, client, mock_duckdb_store):
        """Test that long text is truncated to snippet."""
        long_text = "A" * 300  # 300 characters
        now = datetime.now()

        mock_duckdb_store._data = [{
            "conversation_id": "conv-long",
            "project_id": "test",
            "title": "Long",
            "created_at": now,
            "updated_at": now,
            "message_count": 5,
            "file_path": "/test/long.jsonl",
            "full_text": long_text,
        }]

        with patch('searchat.api.routers.conversations.deps.get_duckdb_store', return_value=mock_duckdb_store):
            response = client.get("/api/conversations/all")

            assert response.status_code == 200
            data = response.json()

            snippet = data["results"][0]["snippet"]
            assert len(snippet) == 203  # 200 chars + "..."
            assert snippet.endswith("...")

    def test_get_all_conversations_error_handling(self, client):
        """Test error handling when store fails."""
        mock_store = Mock()
        mock_store.list_conversations.side_effect = Exception("Database error")

        with patch('searchat.api.routers.conversations.deps.get_duckdb_store', return_value=mock_store):
            response = client.get("/api/conversations/all")

            assert response.status_code == 500
            assert "Database error" in response.json()["detail"]

    def test_get_all_conversations_filter_by_project(self, client, mock_duckdb_store):
        """Test filtering conversations by project."""
        with patch('searchat.api.routers.conversations.deps.get_duckdb_store', return_value=mock_duckdb_store):
            response = client.get("/api/conversations/all?project=project-a")

            assert response.status_code == 200
            data = response.json()

            # Only project-a conversations (conv-3 has 0 messages so filtered out)
            assert data["total"] == 1
            assert data["results"][0]["conversation_id"] == "conv-1"
            assert data["results"][0]["project_id"] == "project-a"

    def test_get_all_conversations_filter_by_project_no_results(self, client, mock_duckdb_store):
        """Test filtering by project with no matching conversations."""
        with patch('searchat.api.routers.conversations.deps.get_duckdb_store', return_value=mock_duckdb_store):
            response = client.get("/api/conversations/all?project=nonexistent-project")

            assert response.status_code == 200
            data = response.json()

            assert data["total"] == 0
            assert len(data["results"]) == 0

    def test_get_all_conversations_filter_by_date_today(self, client, mock_duckdb_store):
        """Test filtering conversations from today."""
        from datetime import timedelta

        now = datetime.now()
        yesterday = now - timedelta(days=1)

        mock_duckdb_store._data = [
            {
                "conversation_id": "conv-today",
                "project_id": "project-a",
                "title": "Today",
                "created_at": now,
                "updated_at": now,
                "message_count": 5,
                "file_path": "/test/today.jsonl",
                "full_text": "Today conversation",
            },
            {
                "conversation_id": "conv-yesterday",
                "project_id": "project-a",
                "title": "Yesterday",
                "created_at": yesterday,
                "updated_at": yesterday,
                "message_count": 5,
                "file_path": "/test/yesterday.jsonl",
                "full_text": "Yesterday conversation",
            },
        ]

        with patch('searchat.api.routers.conversations.deps.get_duckdb_store', return_value=mock_duckdb_store):
            response = client.get("/api/conversations/all?date=today")

            assert response.status_code == 200
            data = response.json()

            # Should only have today's conversation
            assert data["total"] == 1
            assert data["results"][0]["conversation_id"] == "conv-today"

    def test_get_all_conversations_filter_by_date_week(self, client, mock_duckdb_store):
        """Test filtering conversations from last 7 days."""
        from datetime import timedelta

        now = datetime.now()
        five_days_ago = now - timedelta(days=5)
        ten_days_ago = now - timedelta(days=10)

        mock_duckdb_store._data = [
            {
                "conversation_id": "conv-recent",
                "project_id": "project-a",
                "title": "Recent",
                "created_at": five_days_ago,
                "updated_at": five_days_ago,
                "message_count": 5,
                "file_path": "/test/recent.jsonl",
                "full_text": "Recent conversation",
            },
            {
                "conversation_id": "conv-old",
                "project_id": "project-a",
                "title": "Old",
                "created_at": ten_days_ago,
                "updated_at": ten_days_ago,
                "message_count": 5,
                "file_path": "/test/old.jsonl",
                "full_text": "Old conversation",
            },
        ]

        with patch('searchat.api.routers.conversations.deps.get_duckdb_store', return_value=mock_duckdb_store):
            response = client.get("/api/conversations/all?date=week")

            assert response.status_code == 200
            data = response.json()

            # Should only have conversation from last 7 days
            assert data["total"] == 1
            assert data["results"][0]["conversation_id"] == "conv-recent"

    def test_get_all_conversations_filter_by_date_month(self, client, mock_duckdb_store):
        """Test filtering conversations from last 30 days."""
        from datetime import timedelta

        now = datetime.now()
        twenty_days_ago = now - timedelta(days=20)
        forty_days_ago = now - timedelta(days=40)

        mock_duckdb_store._data = [
            {
                "conversation_id": "conv-recent",
                "project_id": "project-a",
                "title": "Recent",
                "created_at": twenty_days_ago,
                "updated_at": twenty_days_ago,
                "message_count": 5,
                "file_path": "/test/recent.jsonl",
                "full_text": "Recent conversation",
            },
            {
                "conversation_id": "conv-old",
                "project_id": "project-a",
                "title": "Old",
                "created_at": forty_days_ago,
                "updated_at": forty_days_ago,
                "message_count": 5,
                "file_path": "/test/old.jsonl",
                "full_text": "Old conversation",
            },
        ]

        with patch('searchat.api.routers.conversations.deps.get_duckdb_store', return_value=mock_duckdb_store):
            response = client.get("/api/conversations/all?date=month")

            assert response.status_code == 200
            data = response.json()

            # Should only have conversation from last 30 days
            assert data["total"] == 1
            assert data["results"][0]["conversation_id"] == "conv-recent"

    def test_get_all_conversations_filter_by_custom_date_range(self, client, mock_duckdb_store):
        """Test filtering conversations with custom date range."""
        mock_duckdb_store._data = [
            {
                "conversation_id": "conv-jan-10",
                "project_id": "project-a",
                "title": "Jan 10",
                "created_at": datetime(2025, 1, 10),
                "updated_at": datetime(2025, 1, 10),
                "message_count": 5,
                "file_path": "/test/jan10.jsonl",
                "full_text": "Jan 10 conversation",
            },
            {
                "conversation_id": "conv-jan-15",
                "project_id": "project-a",
                "title": "Jan 15",
                "created_at": datetime(2025, 1, 15),
                "updated_at": datetime(2025, 1, 15),
                "message_count": 5,
                "file_path": "/test/jan15.jsonl",
                "full_text": "Jan 15 conversation",
            },
            {
                "conversation_id": "conv-jan-20",
                "project_id": "project-a",
                "title": "Jan 20",
                "created_at": datetime(2025, 1, 20),
                "updated_at": datetime(2025, 1, 20),
                "message_count": 5,
                "file_path": "/test/jan20.jsonl",
                "full_text": "Jan 20 conversation",
            },
        ]

        with patch('searchat.api.routers.conversations.deps.get_duckdb_store', return_value=mock_duckdb_store):
            response = client.get("/api/conversations/all?date=custom&date_from=2025-01-12&date_to=2025-01-18")

            assert response.status_code == 200
            data = response.json()

            # Should only have Jan 15 (between Jan 12 and Jan 18 inclusive)
            assert data["total"] == 1
            assert data["results"][0]["conversation_id"] == "conv-jan-15"

    def test_get_all_conversations_filter_combined(self, client, mock_duckdb_store):
        """Test filtering by both project and date."""
        from datetime import timedelta

        now = datetime.now()
        yesterday = now - timedelta(days=1)

        mock_duckdb_store._data = [
            {
                "conversation_id": "conv-a-today",
                "project_id": "project-a",
                "title": "A Today",
                "created_at": now,
                "updated_at": now,
                "message_count": 5,
                "file_path": "/test/a-today.jsonl",
                "full_text": "Project A today",
            },
            {
                "conversation_id": "conv-a-yesterday",
                "project_id": "project-a",
                "title": "A Yesterday",
                "created_at": yesterday,
                "updated_at": yesterday,
                "message_count": 5,
                "file_path": "/test/a-yesterday.jsonl",
                "full_text": "Project A yesterday",
            },
            {
                "conversation_id": "conv-b-today",
                "project_id": "project-b",
                "title": "B Today",
                "created_at": now,
                "updated_at": now,
                "message_count": 5,
                "file_path": "/test/b-today.jsonl",
                "full_text": "Project B today",
            },
        ]

        with patch('searchat.api.routers.conversations.deps.get_duckdb_store', return_value=mock_duckdb_store):
            response = client.get("/api/conversations/all?project=project-a&date=today")

            assert response.status_code == 200
            data = response.json()

            # Should only have project-a from today
            assert data["total"] == 1
            assert data["results"][0]["conversation_id"] == "conv-a-today"


@pytest.mark.unit
class TestGetConversationEndpoint:
    """Tests for GET /api/conversation/{conversation_id} endpoint."""

    def test_get_conversation_success(self, client, mock_duckdb_store, tmp_path):
        """Test successfully retrieving a conversation."""
        # Create temporary JSONL file
        conv_file = tmp_path / "conv-1.jsonl"
        messages = [
            {"type": "user", "message": {"content": "Hello"}, "timestamp": "2025-01-01T10:00:00"},
            {"type": "assistant", "message": {"content": "Hi there!"}, "timestamp": "2025-01-01T10:00:05"}
        ]
        with open(conv_file, 'w') as f:
            for msg in messages:
                f.write(json.dumps(msg) + '\n')

        # Update mock meta to point to temp file
        for row in mock_duckdb_store._data:
            if row["conversation_id"] == "conv-1":
                row["file_path"] = str(conv_file)

        with patch('searchat.api.routers.conversations.deps.get_duckdb_store', return_value=mock_duckdb_store):
            response = client.get("/api/conversation/conv-1")

            assert response.status_code == 200
            data = response.json()

            assert data["conversation_id"] == "conv-1"
            assert data["title"] == "Python Binary Search"
            assert data["message_count"] == 2
            assert len(data["messages"]) == 2
            assert data["messages"][0]["role"] == "user"
            assert data["messages"][0]["content"] == "Hello"
            assert data["messages"][1]["role"] == "assistant"
            assert data["messages"][1]["content"] == "Hi there!"

    def test_get_conversation_not_in_index(self, client, mock_duckdb_store):
        """Test error when conversation not found in index."""
        with patch('searchat.api.routers.conversations.deps.get_duckdb_store', return_value=mock_duckdb_store):
            response = client.get("/api/conversation/nonexistent")

            assert response.status_code == 404
            assert "not found in index" in response.json()["detail"]

    def test_get_conversation_file_not_found(self, client, mock_duckdb_store):
        """Test error when conversation file doesn't exist."""
        with patch('searchat.api.routers.conversations.deps.get_duckdb_store', return_value=mock_duckdb_store):
            # conv-1 exists in index but file doesn't exist
            response = client.get("/api/conversation/conv-1")

            assert response.status_code == 404
            assert "file not found" in response.json()["detail"].lower()

    def test_get_conversation_invalid_json(self, client, mock_duckdb_store, tmp_path):
        """Test error handling for invalid JSON in conversation file."""
        conv_file = tmp_path / "invalid.jsonl"
        with open(conv_file, 'w') as f:
            f.write("invalid json\n")

        for row in mock_duckdb_store._data:
            if row["conversation_id"] == "conv-1":
                row["file_path"] = str(conv_file)

        with patch('searchat.api.routers.conversations.deps.get_duckdb_store', return_value=mock_duckdb_store):
            response = client.get("/api/conversation/conv-1")

            assert response.status_code == 500
            assert "invalid JSON" in response.json()["detail"]

    def test_get_conversation_with_list_content(self, client, mock_duckdb_store, tmp_path):
        """Test handling of content as list (text blocks)."""
        conv_file = tmp_path / "conv-list.jsonl"
        messages = [
            {
                "type": "user",
                "message": {
                    "content": [
                        {"type": "text", "text": "First block"},
                        {"type": "text", "text": "Second block"}
                    ]
                },
                "timestamp": "2025-01-01T10:00:00"
            }
        ]
        with open(conv_file, 'w') as f:
            for msg in messages:
                f.write(json.dumps(msg) + '\n')

        for row in mock_duckdb_store._data:
            if row["conversation_id"] == "conv-1":
                row["file_path"] = str(conv_file)

        with patch('searchat.api.routers.conversations.deps.get_duckdb_store', return_value=mock_duckdb_store):
            response = client.get("/api/conversation/conv-1")

            assert response.status_code == 200
            data = response.json()

            # Content from list should be joined with newlines
            assert "First block\n\nSecond block" in data["messages"][0]["content"]

    def test_get_conversation_skips_non_user_assistant_messages(self, client, mock_duckdb_store, tmp_path):
        """Test that only user/assistant messages are included."""
        conv_file = tmp_path / "conv-mixed.jsonl"
        messages = [
            {"type": "user", "message": {"content": "User message"}, "timestamp": "2025-01-01T10:00:00"},
            {"type": "system", "message": {"content": "System message"}, "timestamp": "2025-01-01T10:00:01"},
            {"type": "assistant", "message": {"content": "Assistant message"}, "timestamp": "2025-01-01T10:00:02"}
        ]
        with open(conv_file, 'w') as f:
            for msg in messages:
                f.write(json.dumps(msg) + '\n')

        for row in mock_duckdb_store._data:
            if row["conversation_id"] == "conv-1":
                row["file_path"] = str(conv_file)

        with patch('searchat.api.routers.conversations.deps.get_duckdb_store', return_value=mock_duckdb_store):
            response = client.get("/api/conversation/conv-1")

            assert response.status_code == 200
            data = response.json()

            # Should only have 2 messages (user and assistant, not system)
            assert len(data["messages"]) == 2
            assert data["messages"][0]["role"] == "user"
            assert data["messages"][1]["role"] == "assistant"


@pytest.mark.unit
class TestResumeSessionEndpoint:
    """Tests for POST /api/resume endpoint."""

    def test_resume_claude_session_success(self, client, mock_duckdb_store, mock_platform_manager, tmp_path):
        """Test successfully resuming a Claude Code session."""
        # Create Claude JSONL file with cwd
        conv_file = tmp_path / "conv-1.jsonl"
        messages = [
            {"type": "user", "cwd": "/home/user/project", "message": {"content": "Test"}},
            {"type": "assistant", "message": {"content": "Response"}}
        ]
        with open(conv_file, 'w') as f:
            for msg in messages:
                f.write(json.dumps(msg) + '\n')

        for row in mock_duckdb_store._data:
            if row["conversation_id"] == "conv-1":
                row["file_path"] = str(conv_file)

        with patch('searchat.api.routers.conversations.deps.get_duckdb_store', return_value=mock_duckdb_store):
            with patch('searchat.api.routers.conversations.get_platform_manager', return_value=mock_platform_manager):
                response = client.post("/api/resume", json={"conversation_id": "conv-1"})

                assert response.status_code == 200
                data = response.json()

                assert data["success"] is True
                assert data["tool"] == "claude"
                assert data["cwd"] == "/home/user/project"
                assert "claude --resume conv-1" in data["command"]
                assert data["platform"] == "windows"

                # Verify terminal was opened
                mock_platform_manager.open_terminal_with_command.assert_called_once()

    def test_resume_vibe_session_success(self, client, mock_duckdb_store, mock_platform_manager, tmp_path):
        """Test successfully resuming a Vibe session."""
        # Create Vibe JSON file
        conv_file = tmp_path / "session_123.json"
        vibe_data = {
            "metadata": {
                "environment": {
                    "working_directory": "/home/user/vibe-project"
                }
            },
            "messages": []
        }
        with open(conv_file, 'w') as f:
            json.dump(vibe_data, f)

        now = datetime.now()
        mock_duckdb_store._data.append({
            "conversation_id": "session_123",
            "project_id": "vibe-project",
            "title": "Vibe Session",
            "created_at": now,
            "updated_at": now,
            "message_count": 5,
            "file_path": str(conv_file),
            "full_text": "Vibe conversation",
        })

        with patch('searchat.api.routers.conversations.deps.get_duckdb_store', return_value=mock_duckdb_store):
            with patch('searchat.api.routers.conversations.get_platform_manager', return_value=mock_platform_manager):
                response = client.post("/api/resume", json={"conversation_id": "session_123"})

                assert response.status_code == 200
                data = response.json()

                assert data["success"] is True
                assert data["tool"] == "vibe"
                assert data["cwd"] == "/home/user/vibe-project"
                assert "vibe --resume session_123" in data["command"]

    def test_resume_conversation_not_found(self, client, mock_duckdb_store, mock_platform_manager):
        """Test error when conversation doesn't exist."""
        with patch('searchat.api.routers.conversations.deps.get_duckdb_store', return_value=mock_duckdb_store):
            with patch('searchat.api.routers.conversations.get_platform_manager', return_value=mock_platform_manager):
                response = client.post("/api/resume", json={"conversation_id": "nonexistent"})

                assert response.status_code == 404
                assert "not found" in response.json()["detail"]

    def test_resume_unknown_format(self, client, mock_duckdb_store, mock_platform_manager, tmp_path):
        """Test error for unknown conversation format."""
        # Create file with unknown extension
        conv_file = tmp_path / "conv.txt"
        conv_file.write_text("unknown format")

        for row in mock_duckdb_store._data:
            if row["conversation_id"] == "conv-1":
                row["file_path"] = str(conv_file)

        with patch('searchat.api.routers.conversations.deps.get_duckdb_store', return_value=mock_duckdb_store):
            with patch('searchat.api.routers.conversations.get_platform_manager', return_value=mock_platform_manager):
                response = client.post("/api/resume", json={"conversation_id": "conv-1"})

                assert response.status_code == 400
                assert "Unknown conversation format" in response.json()["detail"]

    def test_resume_with_path_normalization(self, client, mock_duckdb_store, mock_platform_manager, tmp_path):
        """Test that paths are normalized for the platform."""
        conv_file = tmp_path / "conv-1.jsonl"
        messages = [{"type": "user", "cwd": "/mnt/c/Users/Test/project", "message": {"content": "Test"}}]
        with open(conv_file, 'w') as f:
            for msg in messages:
                f.write(json.dumps(msg) + '\n')

        for row in mock_duckdb_store._data:
            if row["conversation_id"] == "conv-1":
                row["file_path"] = str(conv_file)

        # Mock normalize_path to convert WSL to Windows
        mock_platform_manager.normalize_path = Mock(return_value="C:\\Users\\Test\\project")

        with patch('searchat.api.routers.conversations.deps.get_duckdb_store', return_value=mock_duckdb_store):
            with patch('searchat.api.routers.conversations.get_platform_manager', return_value=mock_platform_manager):
                response = client.post("/api/resume", json={"conversation_id": "conv-1"})

                assert response.status_code == 200
                data = response.json()

                # Path should be normalized
                assert data["cwd"] == "C:\\Users\\Test\\project"
                mock_platform_manager.normalize_path.assert_called_once_with("/mnt/c/Users/Test/project")

    def test_resume_without_cwd(self, client, mock_duckdb_store, mock_platform_manager, tmp_path):
        """Test resuming when no cwd is found in conversation."""
        conv_file = tmp_path / "conv-1.jsonl"
        messages = [
            {"type": "user", "message": {"content": "Test"}},  # No cwd
            {"type": "assistant", "message": {"content": "Response"}}
        ]
        with open(conv_file, 'w') as f:
            for msg in messages:
                f.write(json.dumps(msg) + '\n')

        for row in mock_duckdb_store._data:
            if row["conversation_id"] == "conv-1":
                row["file_path"] = str(conv_file)

        with patch('searchat.api.routers.conversations.deps.get_duckdb_store', return_value=mock_duckdb_store):
            with patch('searchat.api.routers.conversations.get_platform_manager', return_value=mock_platform_manager):
                response = client.post("/api/resume", json={"conversation_id": "conv-1"})

                assert response.status_code == 200
                data = response.json()

                # cwd should be None
                assert data["cwd"] is None
                # Should still open terminal
                mock_platform_manager.open_terminal_with_command.assert_called_once()
