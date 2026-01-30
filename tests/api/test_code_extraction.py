"""API tests for code extraction endpoint."""
from __future__ import annotations

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from searchat.api.app import app
from searchat.api.models.responses import ConversationMessage


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


def test_get_conversation_code_with_python(client):
    """Test code extraction with Python code blocks."""
    mock_conv = Mock()
    mock_conv.conversation_id = "conv-123"
    mock_conv.title = "Python Tutorial"
    mock_conv.messages = [
        ConversationMessage(
            role="user",
            content="Show me a Python function",
            timestamp="2026-01-28T10:00:00"
        ),
        ConversationMessage(
            role="assistant",
            content="Here's a Python function:\n```python\ndef hello():\n    print('Hello!')\n```",
            timestamp="2026-01-28T10:00:05"
        )
    ]

    with patch("searchat.api.routers.conversations.get_conversation", return_value=mock_conv):
        response = client.get("/api/conversation/conv-123/code")

        assert response.status_code == 200
        data = response.json()

        assert data["conversation_id"] == "conv-123"
        assert data["title"] == "Python Tutorial"
        assert data["total_blocks"] == 1

        block = data["code_blocks"][0]
        assert block["language"] == "python"
        assert block["fence_language"] == "python"
        assert block["language_source"] == "fence"
        assert block["role"] == "assistant"
        assert block["message_index"] == 1
        assert block["block_index"] == 0
        assert "def hello():" in block["code"]
        assert block["lines"] == 2


def test_get_conversation_code_with_multiple_languages(client):
    """Test code extraction with multiple language blocks."""
    mock_conv = Mock()
    mock_conv.conversation_id = "conv-456"
    mock_conv.title = "Multi-language"
    mock_conv.messages = [
        ConversationMessage(
            role="assistant",
            content="Python:\n```python\nprint('hello')\n```\n\nJavaScript:\n```javascript\nconsole.log('hello')\n```",
            timestamp="2026-01-28T10:00:00"
        )
    ]

    with patch("searchat.api.routers.conversations.get_conversation", return_value=mock_conv):
        response = client.get("/api/conversation/conv-456/code")

        assert response.status_code == 200
        data = response.json()

        assert data["total_blocks"] == 2

        # First block (Python)
        assert data["code_blocks"][0]["language"] == "python"
        assert "print('hello')" in data["code_blocks"][0]["code"]

        # Second block (JavaScript)
        assert data["code_blocks"][1]["language"] == "javascript"
        assert "console.log('hello')" in data["code_blocks"][1]["code"]


def test_get_conversation_code_no_language_specified(client):
    """Test code extraction with auto language detection."""
    mock_conv = Mock()
    mock_conv.conversation_id = "conv-789"
    mock_conv.title = "Auto Detect"
    mock_conv.messages = [
        ConversationMessage(
            role="assistant",
            content="Here's the code:\n```\ndef test():\n    pass\n```",
            timestamp="2026-01-28T10:00:00"
        )
    ]

    with patch("searchat.api.routers.conversations.get_conversation", return_value=mock_conv):
        response = client.get("/api/conversation/conv-789/code")

        assert response.status_code == 200
        data = response.json()

        assert data["total_blocks"] == 1
        # Should auto-detect as Python
        assert data["code_blocks"][0]["language"] == "python"
        assert data["code_blocks"][0]["fence_language"] is None
        assert data["code_blocks"][0]["language_source"] == "detected"


def test_get_conversation_code_empty_blocks_filtered(client):
    """Test that empty code blocks are filtered out."""
    mock_conv = Mock()
    mock_conv.conversation_id = "conv-empty"
    mock_conv.title = "Empty Blocks"
    mock_conv.messages = [
        ConversationMessage(
            role="assistant",
            content="Empty:\n```python\n\n```\n\nValid:\n```python\nprint('test')\n```",
            timestamp="2026-01-28T10:00:00"
        )
    ]

    with patch("searchat.api.routers.conversations.get_conversation", return_value=mock_conv):
        response = client.get("/api/conversation/conv-empty/code")

        assert response.status_code == 200
        data = response.json()

        # Should only have the valid block
        assert data["total_blocks"] == 1
        assert "print('test')" in data["code_blocks"][0]["code"]


def test_get_conversation_code_no_code_blocks(client):
    """Test code extraction when no code blocks exist."""
    mock_conv = Mock()
    mock_conv.conversation_id = "conv-nocode"
    mock_conv.title = "No Code"
    mock_conv.messages = [
        ConversationMessage(
            role="user",
            content="Just plain text, no code here",
            timestamp="2026-01-28T10:00:00"
        )
    ]

    with patch("searchat.api.routers.conversations.get_conversation", return_value=mock_conv):
        response = client.get("/api/conversation/conv-nocode/code")

        assert response.status_code == 200
        data = response.json()

        assert data["total_blocks"] == 0
        assert data["code_blocks"] == []


def test_get_conversation_code_multiple_blocks_per_message(client):
    """Test extraction of multiple code blocks from single message."""
    mock_conv = Mock()
    mock_conv.conversation_id = "conv-multi"
    mock_conv.title = "Multiple Blocks"
    mock_conv.messages = [
        ConversationMessage(
            role="assistant",
            content="First:\n```python\ncode1\n```\nSecond:\n```python\ncode2\n```\nThird:\n```python\ncode3\n```",
            timestamp="2026-01-28T10:00:00"
        )
    ]

    with patch("searchat.api.routers.conversations.get_conversation", return_value=mock_conv):
        response = client.get("/api/conversation/conv-multi/code")

        assert response.status_code == 200
        data = response.json()

        assert data["total_blocks"] == 3
        assert data["code_blocks"][0]["block_index"] == 0
        assert data["code_blocks"][1]["block_index"] == 1
        assert data["code_blocks"][2]["block_index"] == 2


def test_get_conversation_code_with_timestamps(client):
    """Test code blocks include message timestamps."""
    mock_conv = Mock()
    mock_conv.conversation_id = "conv-time"
    mock_conv.title = "Timestamps"
    mock_conv.messages = [
        ConversationMessage(
            role="assistant",
            content="```python\ncode\n```",
            timestamp="2026-01-28T10:30:00"
        )
    ]

    with patch("searchat.api.routers.conversations.get_conversation", return_value=mock_conv):
        response = client.get("/api/conversation/conv-time/code")

        assert response.status_code == 200
        data = response.json()

        assert data["code_blocks"][0]["timestamp"] == "2026-01-28T10:30:00"


def test_get_conversation_code_line_count(client):
    """Test code blocks include correct line count."""
    mock_conv = Mock()
    mock_conv.conversation_id = "conv-lines"
    mock_conv.title = "Line Count"
    mock_conv.messages = [
        ConversationMessage(
            role="assistant",
            content="```python\nline1\nline2\nline3\nline4\nline5\n```",
            timestamp="2026-01-28T10:00:00"
        )
    ]

    with patch("searchat.api.routers.conversations.get_conversation", return_value=mock_conv):
        response = client.get("/api/conversation/conv-lines/code")

        assert response.status_code == 200
        data = response.json()

        assert data["code_blocks"][0]["lines"] == 5


def test_get_conversation_code_language_detection_javascript(client):
    """Test JavaScript language detection."""
    mock_conv = Mock()
    mock_conv.conversation_id = "conv-js"
    mock_conv.title = "JS Detection"
    mock_conv.messages = [
        ConversationMessage(
            role="assistant",
            content="```\nconst x = () => console.log('test');\n```",
            timestamp="2026-01-28T10:00:00"
        )
    ]

    with patch("searchat.api.routers.conversations.get_conversation", return_value=mock_conv):
        response = client.get("/api/conversation/conv-js/code")

        assert response.status_code == 200
        data = response.json()

        assert data["code_blocks"][0]["language"] == "javascript"


def test_get_conversation_code_language_detection_bash(client):
    """Test Bash language detection."""
    mock_conv = Mock()
    mock_conv.conversation_id = "conv-bash"
    mock_conv.title = "Bash Detection"
    mock_conv.messages = [
        ConversationMessage(
            role="assistant",
            content="```\n#!/bin/bash\necho 'test'\n```",
            timestamp="2026-01-28T10:00:00"
        )
    ]

    with patch("searchat.api.routers.conversations.get_conversation", return_value=mock_conv):
        response = client.get("/api/conversation/conv-bash/code")

        assert response.status_code == 200
        data = response.json()

        assert data["code_blocks"][0]["language"] == "bash"


def test_get_conversation_code_language_detection_sql(client):
    """Test SQL language detection."""
    mock_conv = Mock()
    mock_conv.conversation_id = "conv-sql"
    mock_conv.title = "SQL Detection"
    mock_conv.messages = [
        ConversationMessage(
            role="assistant",
            content="```\nSELECT * FROM users WHERE id = 1;\n```",
            timestamp="2026-01-28T10:00:00"
        )
    ]

    with patch("searchat.api.routers.conversations.get_conversation", return_value=mock_conv):
        response = client.get("/api/conversation/conv-sql/code")

        assert response.status_code == 200
        data = response.json()

        assert data["code_blocks"][0]["language"] == "sql"


def test_get_conversation_code_language_detection_plaintext(client):
    """Test fallback to plaintext for unknown language."""
    mock_conv = Mock()
    mock_conv.conversation_id = "conv-plain"
    mock_conv.title = "Plaintext"
    mock_conv.messages = [
        ConversationMessage(
            role="assistant",
            content="```\njust some random text\nwith no identifiable syntax\n```",
            timestamp="2026-01-28T10:00:00"
        )
    ]

    with patch("searchat.api.routers.conversations.get_conversation", return_value=mock_conv):
        response = client.get("/api/conversation/conv-plain/code")

        assert response.status_code == 200
        data = response.json()

        assert data["code_blocks"][0]["language"] == "plaintext"


def test_get_conversation_code_nonexistent(client):
    """Test code extraction for nonexistent conversation."""
    from fastapi import HTTPException

    def mock_get_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")

    with patch("searchat.api.routers.conversations.get_conversation", side_effect=mock_get_conversation):
        response = client.get("/api/conversation/nonexistent/code")

        assert response.status_code == 404


def test_get_conversation_code_message_index(client):
    """Test code blocks track correct message index."""
    mock_conv = Mock()
    mock_conv.conversation_id = "conv-idx"
    mock_conv.title = "Message Index"
    mock_conv.messages = [
        ConversationMessage(role="user", content="no code", timestamp="2026-01-28T10:00:00"),
        ConversationMessage(role="assistant", content="```python\ncode1\n```", timestamp="2026-01-28T10:00:05"),
        ConversationMessage(role="user", content="more questions", timestamp="2026-01-28T10:00:10"),
        ConversationMessage(role="assistant", content="```python\ncode2\n```", timestamp="2026-01-28T10:00:15"),
    ]

    with patch("searchat.api.routers.conversations.get_conversation", return_value=mock_conv):
        response = client.get("/api/conversation/conv-idx/code")

        assert response.status_code == 200
        data = response.json()

        assert data["total_blocks"] == 2
        assert data["code_blocks"][0]["message_index"] == 1
        assert data["code_blocks"][1]["message_index"] == 3


def test_get_conversation_code_role_tracking(client):
    """Test code blocks track message role (user/assistant)."""
    mock_conv = Mock()
    mock_conv.conversation_id = "conv-role"
    mock_conv.title = "Role Tracking"
    mock_conv.messages = [
        ConversationMessage(role="user", content="```python\nuser_code\n```", timestamp="2026-01-28T10:00:00"),
        ConversationMessage(role="assistant", content="```python\nassistant_code\n```", timestamp="2026-01-28T10:00:05"),
    ]

    with patch("searchat.api.routers.conversations.get_conversation", return_value=mock_conv):
        response = client.get("/api/conversation/conv-role/code")

        assert response.status_code == 200
        data = response.json()

        assert data["code_blocks"][0]["role"] == "user"
        assert data["code_blocks"][1]["role"] == "assistant"
