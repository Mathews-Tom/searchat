from __future__ import annotations

import json
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from searchat.api.app import app
from searchat.api.models.responses import ConversationMessage


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def export_config_disabled():
    cfg = Mock()
    cfg.export = Mock(enable_ipynb=False, enable_pdf=False, enable_tech_docs=False)
    return cfg


@pytest.fixture
def export_config_enabled():
    cfg = Mock()
    cfg.export = Mock(enable_ipynb=True, enable_pdf=True, enable_tech_docs=False)
    return cfg


def test_export_ipynb_disabled_returns_404(client, export_config_disabled):
    mock_conv = Mock()
    mock_conv.conversation_id = "conv-123"
    mock_conv.title = "Test"
    mock_conv.project_id = "p"
    mock_conv.project_path = None
    mock_conv.tool = "claude"
    mock_conv.message_count = 1
    mock_conv.messages = [ConversationMessage(role="user", content="hi", timestamp="")] 

    with patch("searchat.api.routers.conversations.get_conversation", return_value=mock_conv):
        with patch("searchat.api.routers.conversations.deps.get_config", return_value=export_config_disabled):
            resp = client.get("/api/conversation/conv-123/export?format=ipynb")

    assert resp.status_code == 404


def test_export_ipynb_enabled_returns_valid_notebook(client, export_config_enabled):
    mock_conv = Mock()
    mock_conv.conversation_id = "conv-123"
    mock_conv.title = "Notebook Test"
    mock_conv.project_id = "p"
    mock_conv.project_path = None
    mock_conv.tool = "claude"
    mock_conv.message_count = 1
    mock_conv.messages = [
        ConversationMessage(
            role="assistant",
            content="Text before\n```python\nprint('hi')\n```\nText after",
            timestamp="2026-01-28T10:00:00",
        )
    ]

    with patch("searchat.api.routers.conversations.get_conversation", return_value=mock_conv):
        with patch("searchat.api.routers.conversations.deps.get_config", return_value=export_config_enabled):
            resp = client.get("/api/conversation/conv-123/export?format=ipynb")

    assert resp.status_code == 200
    assert "application/x-ipynb+json" in resp.headers["content-type"]

    nb = json.loads(resp.content)
    assert nb["nbformat"] == 4
    assert isinstance(nb["cells"], list)
    assert nb["cells"]


def test_export_pdf_disabled_returns_404(client, export_config_disabled):
    mock_conv = Mock()
    mock_conv.conversation_id = "conv-123"
    mock_conv.title = "Test"
    mock_conv.project_id = "p"
    mock_conv.project_path = None
    mock_conv.tool = "claude"
    mock_conv.message_count = 1
    mock_conv.messages = [ConversationMessage(role="user", content="hi", timestamp="")]

    with patch("searchat.api.routers.conversations.get_conversation", return_value=mock_conv):
        with patch("searchat.api.routers.conversations.deps.get_config", return_value=export_config_disabled):
            resp = client.get("/api/conversation/conv-123/export?format=pdf")

    assert resp.status_code == 404


def test_export_pdf_enabled_returns_pdf_bytes(client, export_config_enabled):
    mock_conv = Mock()
    mock_conv.conversation_id = "conv-123"
    mock_conv.title = "PDF Test"
    mock_conv.project_id = "p"
    mock_conv.project_path = None
    mock_conv.tool = "claude"
    mock_conv.message_count = 1
    mock_conv.messages = [
        ConversationMessage(
            role="assistant",
            content="```python\ndef hello():\n    return 1\n```",
            timestamp="2026-01-28T10:00:00",
        )
    ]

    with patch("searchat.api.routers.conversations.get_conversation", return_value=mock_conv):
        with patch("searchat.api.routers.conversations.deps.get_config", return_value=export_config_enabled):
            resp = client.get("/api/conversation/conv-123/export?format=pdf")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


def test_bulk_export_ipynb_disabled_returns_404(client, export_config_disabled):
    with patch("searchat.api.routers.conversations.deps.get_config", return_value=export_config_disabled):
        resp = client.post(
            "/api/conversations/bulk-export",
            json={"conversation_ids": ["conv-1"], "format": "ipynb"},
        )
    assert resp.status_code == 404
