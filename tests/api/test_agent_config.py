from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from searchat.api.app import app
from searchat.services.pattern_mining import ExtractedPattern, PatternEvidence


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_patterns():
    """Sample extracted patterns for testing."""
    return [
        ExtractedPattern(
            name="Test-Driven Development",
            description="User consistently writes tests before implementation",
            evidence=[
                PatternEvidence(
                    conversation_id="conv-123",
                    date="2025-01-15",
                    snippet="I always write the test first to verify expected behavior and ensure code quality",
                ),
                PatternEvidence(
                    conversation_id="conv-456",
                    date="2025-01-20",
                    snippet="Let's start with a failing test case that defines the expected interface",
                ),
                PatternEvidence(
                    conversation_id="conv-789",
                    date="2025-01-22",
                    snippet="Before implementing the feature, let's add comprehensive test coverage",
                ),
            ],
            confidence=0.92,
        ),
        ExtractedPattern(
            name="Code Review Preference",
            description="User prefers detailed code reviews with explanations",
            evidence=[
                PatternEvidence(
                    conversation_id="conv-111",
                    date="2025-01-18",
                    snippet="Can you explain why this approach is better than the alternative?",
                ),
            ],
            confidence=0.85,
        ),
    ]


def test_generate_agent_config_success_claude_md(client, mock_patterns):
    """Test successful agent config generation with claude.md format."""
    config = Mock()

    with patch("searchat.api.routers.docs.deps.get_config", return_value=config):
        with patch(
            "searchat.api.routers.docs.extract_patterns", return_value=mock_patterns
        ) as mock_extract:
            resp = client.post(
                "/api/export/agent-config",
                json={
                    "format": "claude.md",
                    "project_filter": "my-project",
                    "model_provider": "ollama",
                    "model_name": "llama3",
                },
            )

    assert resp.status_code == 200
    data = resp.json()

    assert data["format"] == "claude.md"
    assert data["pattern_count"] == 2
    assert data["project_filter"] == "my-project"

    # Verify content structure
    content = data["content"]
    assert "# my-project — CLAUDE.md" in content
    assert "## Conventions" in content
    assert "Test-Driven Development" in content
    assert "Code Review Preference" in content
    assert "User consistently writes tests" in content

    # Verify extraction was called with correct parameters
    mock_extract.assert_called_once()
    _, kwargs = mock_extract.call_args
    assert kwargs["topic"] == "my-project"
    assert kwargs["max_patterns"] == 15
    assert kwargs["model_provider"] == "ollama"
    assert kwargs["model_name"] == "llama3"


def test_generate_agent_config_success_copilot_instructions(client, mock_patterns):
    """Test successful agent config generation with copilot-instructions.md format."""
    config = Mock()

    with patch("searchat.api.routers.docs.deps.get_config", return_value=config):
        with patch(
            "searchat.api.routers.docs.extract_patterns", return_value=mock_patterns
        ):
            resp = client.post(
                "/api/export/agent-config",
                json={
                    "format": "copilot-instructions.md",
                    "project_filter": "test-project",
                    "model_provider": "openai",
                },
            )

    assert resp.status_code == 200
    data = resp.json()

    assert data["format"] == "copilot-instructions.md"
    assert data["pattern_count"] == 2

    content = data["content"]
    assert "# test-project — Copilot Instructions" in content
    assert "Test-Driven Development" in content


def test_generate_agent_config_success_cursorrules(client, mock_patterns):
    """Test successful agent config generation with cursorrules format."""
    config = Mock()

    with patch("searchat.api.routers.docs.deps.get_config", return_value=config):
        with patch(
            "searchat.api.routers.docs.extract_patterns", return_value=mock_patterns
        ):
            resp = client.post(
                "/api/export/agent-config",
                json={
                    "format": "cursorrules",
                    "project_filter": None,
                    "model_provider": "embedded",
                },
            )

    assert resp.status_code == 200
    data = resp.json()

    assert data["format"] == "cursorrules"
    assert data["pattern_count"] == 2
    assert data["project_filter"] is None

    content = data["content"]
    assert "# Project" in content
    assert "Test-Driven Development" in content


def test_generate_agent_config_invalid_provider(client):
    """Test agent config generation with invalid provider."""
    resp = client.post(
        "/api/export/agent-config",
        json={
            "format": "claude.md",
            "project_filter": "test",
            "model_provider": "invalid_provider",
        },
    )

    assert resp.status_code == 400
    assert "model_provider must be" in resp.json()["detail"]


def test_generate_agent_config_pattern_extraction_error(client):
    """Test agent config generation when pattern extraction fails."""
    config = Mock()

    with patch("searchat.api.routers.docs.deps.get_config", return_value=config):
        with patch(
            "searchat.api.routers.docs.extract_patterns",
            side_effect=RuntimeError("Pattern extraction failed"),
        ):
            resp = client.post(
                "/api/export/agent-config",
                json={
                    "format": "claude.md",
                    "project_filter": "test",
                    "model_provider": "ollama",
                },
            )

    assert resp.status_code == 500
    assert "Pattern extraction failed" in resp.json()["detail"]


def test_generate_agent_config_default_format(client, mock_patterns):
    """Test agent config generation with default format (claude.md)."""
    config = Mock()

    with patch("searchat.api.routers.docs.deps.get_config", return_value=config):
        with patch(
            "searchat.api.routers.docs.extract_patterns", return_value=mock_patterns
        ):
            resp = client.post(
                "/api/export/agent-config",
                json={
                    "model_provider": "ollama",
                },
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["format"] == "claude.md"


def test_generate_agent_config_default_provider(client, mock_patterns):
    """Test agent config generation with default provider (ollama)."""
    config = Mock()

    with patch("searchat.api.routers.docs.deps.get_config", return_value=config):
        with patch(
            "searchat.api.routers.docs.extract_patterns", return_value=mock_patterns
        ) as mock_extract:
            resp = client.post(
                "/api/export/agent-config",
                json={
                    "format": "claude.md",
                },
            )

    assert resp.status_code == 200

    mock_extract.assert_called_once()
    _, kwargs = mock_extract.call_args
    assert kwargs["model_provider"] == "ollama"


def test_generate_agent_config_no_patterns(client):
    """Test agent config generation when no patterns are found."""
    config = Mock()

    with patch("searchat.api.routers.docs.deps.get_config", return_value=config):
        with patch("searchat.api.routers.docs.extract_patterns", return_value=[]):
            resp = client.post(
                "/api/export/agent-config",
                json={
                    "format": "claude.md",
                    "project_filter": "empty-project",
                    "model_provider": "ollama",
                },
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["pattern_count"] == 0

    content = data["content"]
    assert "# empty-project — CLAUDE.md" in content
    assert "## Conventions" in content


def test_generate_agent_config_evidence_truncation(client):
    """Test that evidence snippets are truncated to 100 chars in output."""
    long_pattern = ExtractedPattern(
        name="Long Evidence Pattern",
        description="Pattern with very long evidence snippets",
        evidence=[
            PatternEvidence(
                conversation_id="conv-long",
                date="2025-01-25",
                snippet="This is a very long snippet that exceeds one hundred characters and should be truncated in the generated config file to avoid cluttering",
            ),
        ],
        confidence=0.8,
    )
    config = Mock()

    with patch("searchat.api.routers.docs.deps.get_config", return_value=config):
        with patch(
            "searchat.api.routers.docs.extract_patterns", return_value=[long_pattern]
        ):
            resp = client.post(
                "/api/export/agent-config",
                json={
                    "format": "claude.md",
                    "model_provider": "ollama",
                },
            )

    assert resp.status_code == 200
    content = resp.json()["content"]

    # Verify snippet was truncated (100 chars + "...")
    assert "This is a very long snippet that exceeds one hundred characters and should be truncated in the gener..." in content


def test_generate_agent_config_max_evidence_three(client):
    """Test that only first 3 evidence items are included."""
    many_evidence = [
        PatternEvidence(
            conversation_id=f"conv-{i}",
            date=f"2025-01-{10+i:02d}",
            snippet=f"Evidence item {i}",
        )
        for i in range(10)
    ]

    pattern_with_many = ExtractedPattern(
        name="Pattern With Many Evidence",
        description="This pattern has many evidence items",
        evidence=many_evidence,
        confidence=0.95,
    )
    config = Mock()

    with patch("searchat.api.routers.docs.deps.get_config", return_value=config):
        with patch(
            "searchat.api.routers.docs.extract_patterns",
            return_value=[pattern_with_many],
        ):
            resp = client.post(
                "/api/export/agent-config",
                json={
                    "format": "claude.md",
                    "model_provider": "ollama",
                },
            )

    assert resp.status_code == 200
    content = resp.json()["content"]

    # Count how many evidence items appear
    assert "Evidence item 0" in content
    assert "Evidence item 1" in content
    assert "Evidence item 2" in content
    assert "Evidence item 3" not in content
    assert "Evidence item 9" not in content


def test_generate_agent_config_pattern_no_evidence(client):
    """Test agent config generation with pattern that has no evidence."""
    pattern_no_evidence = ExtractedPattern(
        name="Pattern Without Evidence",
        description="This pattern has no supporting evidence",
        evidence=[],
        confidence=0.5,
    )
    config = Mock()

    with patch("searchat.api.routers.docs.deps.get_config", return_value=config):
        with patch(
            "searchat.api.routers.docs.extract_patterns",
            return_value=[pattern_no_evidence],
        ):
            resp = client.post(
                "/api/export/agent-config",
                json={
                    "format": "claude.md",
                    "model_provider": "ollama",
                },
            )

    assert resp.status_code == 200
    content = resp.json()["content"]

    assert "Pattern Without Evidence" in content
    assert "This pattern has no supporting evidence" in content
    # Evidence section should not appear when no evidence
    assert "Evidence:" not in content


def test_generate_agent_config_all_providers(client, mock_patterns):
    """Test agent config generation with all valid providers."""
    config = Mock()

    for provider in ["openai", "ollama", "embedded"]:
        with patch("searchat.api.routers.docs.deps.get_config", return_value=config):
            with patch(
                "searchat.api.routers.docs.extract_patterns", return_value=mock_patterns
            ):
                resp = client.post(
                    "/api/export/agent-config",
                    json={
                        "format": "claude.md",
                        "model_provider": provider,
                    },
                )

        assert resp.status_code == 200, f"Failed for provider: {provider}"
        data = resp.json()
        assert data["pattern_count"] == 2


def test_generate_agent_config_all_formats(client, mock_patterns):
    """Test agent config generation with all valid formats."""
    config = Mock()

    for fmt in ["claude.md", "copilot-instructions.md", "cursorrules"]:
        with patch("searchat.api.routers.docs.deps.get_config", return_value=config):
            with patch(
                "searchat.api.routers.docs.extract_patterns", return_value=mock_patterns
            ):
                resp = client.post(
                    "/api/export/agent-config",
                    json={
                        "format": fmt,
                        "model_provider": "ollama",
                    },
                )

        assert resp.status_code == 200, f"Failed for format: {fmt}"
        data = resp.json()
        assert data["format"] == fmt
        assert data["pattern_count"] == 2


def test_generate_agent_config_invalid_format(client):
    """Test agent config generation with invalid format."""
    resp = client.post(
        "/api/export/agent-config",
        json={
            "format": "invalid.format",
            "model_provider": "ollama",
        },
    )

    assert resp.status_code == 422


def test_generate_agent_config_with_model_name(client, mock_patterns):
    """Test agent config generation with specific model name."""
    config = Mock()

    with patch("searchat.api.routers.docs.deps.get_config", return_value=config):
        with patch(
            "searchat.api.routers.docs.extract_patterns", return_value=mock_patterns
        ) as mock_extract:
            resp = client.post(
                "/api/export/agent-config",
                json={
                    "format": "claude.md",
                    "model_provider": "openai",
                    "model_name": "gpt-4.1",
                },
            )

    assert resp.status_code == 200

    mock_extract.assert_called_once()
    _, kwargs = mock_extract.call_args
    assert kwargs["model_name"] == "gpt-4.1"


def test_generate_agent_config_project_filter_in_content(client, mock_patterns):
    """Test that project filter appears in generated content."""
    config = Mock()

    with patch("searchat.api.routers.docs.deps.get_config", return_value=config):
        with patch(
            "searchat.api.routers.docs.extract_patterns", return_value=mock_patterns
        ):
            resp = client.post(
                "/api/export/agent-config",
                json={
                    "format": "claude.md",
                    "project_filter": "searchat-v2",
                    "model_provider": "ollama",
                },
            )

    assert resp.status_code == 200
    content = resp.json()["content"]

    # Project name should appear in title
    assert "searchat-v2" in content
    assert "# searchat-v2 —" in content


def test_generate_agent_config_value_error_handling(client):
    """Test agent config generation with ValueError from pattern extraction."""
    config = Mock()

    with patch("searchat.api.routers.docs.deps.get_config", return_value=config):
        with patch(
            "searchat.api.routers.docs.extract_patterns",
            side_effect=ValueError("Invalid topic filter"),
        ):
            resp = client.post(
                "/api/export/agent-config",
                json={
                    "format": "claude.md",
                    "project_filter": "test",
                    "model_provider": "ollama",
                },
            )

    assert resp.status_code == 500
    assert "Invalid topic filter" in resp.json()["detail"]
