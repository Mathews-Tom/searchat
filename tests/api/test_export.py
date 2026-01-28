"""API tests for conversation export endpoints."""
from __future__ import annotations

import json
import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from searchat.api.app import app
from searchat.api.models.responses import ConversationMessage


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_conversation_response():
    """Mock conversation response data."""
    mock = Mock()
    mock.conversation_id = "conv-123"
    mock.title = "Test Conversation"
    mock.project_id = "test-project"
    mock.project_path = "/path/to/project"
    mock.tool = "claude"
    mock.message_count = 2
    mock.messages = [
        ConversationMessage(
            role="user",
            content="Hello, how are you?",
            timestamp="2026-01-28T10:00:00"
        ),
        ConversationMessage(
            role="assistant",
            content="I'm doing well, thank you!",
            timestamp="2026-01-28T10:00:05"
        )
    ]
    return mock


def test_export_conversation_json(client, mock_conversation_response):
    """Test GET /api/conversation/{id}/export with JSON format."""
    with patch("searchat.api.routers.conversations.get_conversation", return_value=mock_conversation_response):
        response = client.get("/api/conversation/conv-123/export?format=json")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert 'attachment; filename="conv-123.json"' in response.headers["content-disposition"]

        data = json.loads(response.content)
        assert data["conversation_id"] == "conv-123"
        assert data["title"] == "Test Conversation"
        assert data["project_id"] == "test-project"
        assert data["project_path"] == "/path/to/project"
        assert data["tool"] == "claude"
        assert data["message_count"] == 2
        assert len(data["messages"]) == 2
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][0]["content"] == "Hello, how are you?"


def test_export_conversation_markdown(client, mock_conversation_response):
    """Test GET /api/conversation/{id}/export with Markdown format."""
    with patch("searchat.api.routers.conversations.get_conversation", return_value=mock_conversation_response):
        response = client.get("/api/conversation/conv-123/export?format=markdown")

        assert response.status_code == 200
        assert "text/markdown" in response.headers["content-type"]
        assert 'attachment; filename="conv-123.md"' in response.headers["content-disposition"]

        content = response.content.decode('utf-8')
        assert "# Test Conversation" in content
        assert "**Conversation ID:** conv-123" in content
        assert "**Project:** test-project" in content
        assert "**Project Path:** /path/to/project" in content
        assert "**Tool:** claude" in content
        assert "**Messages:** 2" in content
        assert "## Message 1 - USER" in content
        assert "Hello, how are you?" in content
        assert "## Message 2 - ASSISTANT" in content
        assert "I'm doing well, thank you!" in content


def test_export_conversation_text(client, mock_conversation_response):
    """Test GET /api/conversation/{id}/export with text format."""
    with patch("searchat.api.routers.conversations.get_conversation", return_value=mock_conversation_response):
        response = client.get("/api/conversation/conv-123/export?format=text")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; charset=utf-8"
        assert 'attachment; filename="conv-123.txt"' in response.headers["content-disposition"]

        content = response.content.decode('utf-8')
        assert "CONVERSATION: Test Conversation" in content
        assert "ID: conv-123" in content
        assert "Project: test-project" in content
        assert "Project Path: /path/to/project" in content
        assert "Tool: claude" in content
        assert "Messages: 2" in content
        assert "[Message 1 - USER]" in content
        assert "Hello, how are you?" in content
        assert "[Message 2 - ASSISTANT]" in content
        assert "I'm doing well, thank you!" in content


def test_export_conversation_default_format(client, mock_conversation_response):
    """Test export endpoint defaults to JSON format."""
    with patch("searchat.api.routers.conversations.get_conversation", return_value=mock_conversation_response):
        response = client.get("/api/conversation/conv-123/export")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"


def test_export_conversation_invalid_format(client, mock_conversation_response):
    """Test export endpoint rejects invalid format."""
    with patch("searchat.api.routers.conversations.get_conversation", return_value=mock_conversation_response):
        response = client.get("/api/conversation/conv-123/export?format=xml")

        assert response.status_code == 400
        assert "Invalid format" in response.json()["detail"]


def test_export_conversation_not_found(client):
    """Test export endpoint handles nonexistent conversation."""
    from fastapi import HTTPException

    def mock_get_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")

    with patch("searchat.api.routers.conversations.get_conversation", side_effect=mock_get_conversation):
        response = client.get("/api/conversation/nonexistent/export")

        assert response.status_code == 404


def test_export_conversation_without_project_path(client):
    """Test export handles conversations without project path."""
    mock = Mock()
    mock.conversation_id = "conv-456"
    mock.title = "Test"
    mock.project_id = "project"
    mock.project_path = None  # No project path
    mock.tool = "vibe"
    mock.message_count = 1
    mock.messages = [ConversationMessage(role="user", content="Test", timestamp="2026-01-28T10:00:00")]

    with patch("searchat.api.routers.conversations.get_conversation", return_value=mock):
        # Test markdown (has conditional project path)
        response = client.get("/api/conversation/conv-456/export?format=markdown")
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert "**Project Path:**" not in content

        # Test text (has conditional project path)
        response = client.get("/api/conversation/conv-456/export?format=text")
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert "Project Path:" not in content


def test_export_conversation_case_insensitive_format(client, mock_conversation_response):
    """Test export format parameter is case-insensitive."""
    with patch("searchat.api.routers.conversations.get_conversation", return_value=mock_conversation_response):
        # Test uppercase
        response = client.get("/api/conversation/conv-123/export?format=JSON")
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]

        # Test mixed case
        response = client.get("/api/conversation/conv-123/export?format=MarkDown")
        assert response.status_code == 200
        assert "text/markdown" in response.headers["content-type"]


def test_bulk_export_json(client, mock_conversation_response):
    """Test POST /api/conversations/bulk-export with JSON format."""
    with patch("searchat.api.routers.conversations.get_conversation", return_value=mock_conversation_response):
        response = client.post(
            "/api/conversations/bulk-export",
            json={
                "conversation_ids": ["conv-1", "conv-2"],
                "format": "json"
            }
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        assert "attachment; filename=" in response.headers["content-disposition"]
        assert ".zip" in response.headers["content-disposition"]


def test_bulk_export_markdown(client, mock_conversation_response):
    """Test POST /api/conversations/bulk-export with markdown format."""
    with patch("searchat.api.routers.conversations.get_conversation", return_value=mock_conversation_response):
        response = client.post(
            "/api/conversations/bulk-export",
            json={
                "conversation_ids": ["conv-1"],
                "format": "markdown"
            }
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"


def test_bulk_export_text(client, mock_conversation_response):
    """Test POST /api/conversations/bulk-export with text format."""
    with patch("searchat.api.routers.conversations.get_conversation", return_value=mock_conversation_response):
        response = client.post(
            "/api/conversations/bulk-export",
            json={
                "conversation_ids": ["conv-1", "conv-2", "conv-3"],
                "format": "text"
            }
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"


def test_bulk_export_empty_list(client):
    """Test bulk export rejects empty conversation list."""
    response = client.post(
        "/api/conversations/bulk-export",
        json={
            "conversation_ids": [],
            "format": "json"
        }
    )

    assert response.status_code == 400
    assert "No conversation IDs" in response.json()["detail"]


def test_bulk_export_too_many_conversations(client):
    """Test bulk export enforces maximum limit."""
    response = client.post(
        "/api/conversations/bulk-export",
        json={
            "conversation_ids": [f"conv-{i}" for i in range(101)],
            "format": "json"
        }
    )

    assert response.status_code == 400
    assert "Too many conversations" in response.json()["detail"]


def test_bulk_export_invalid_format(client):
    """Test bulk export rejects invalid format."""
    response = client.post(
        "/api/conversations/bulk-export",
        json={
            "conversation_ids": ["conv-1"],
            "format": "pdf"
        }
    )

    assert response.status_code == 400
    assert "Invalid format" in response.json()["detail"]


def test_bulk_export_default_format(client, mock_conversation_response):
    """Test bulk export defaults to JSON format."""
    with patch("searchat.api.routers.conversations.get_conversation", return_value=mock_conversation_response):
        response = client.post(
            "/api/conversations/bulk-export",
            json={
                "conversation_ids": ["conv-1"]
            }
        )

        assert response.status_code == 200


def test_bulk_export_validation(client):
    """Test bulk export request validation."""
    # Missing conversation_ids
    response = client.post(
        "/api/conversations/bulk-export",
        json={"format": "json"}
    )
    assert response.status_code == 422

    # Invalid JSON
    response = client.post(
        "/api/conversations/bulk-export",
        data="invalid json",
        headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
