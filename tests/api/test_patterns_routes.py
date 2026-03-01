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
                    snippet="I always write the test first to verify expected behavior",
                ),
                PatternEvidence(
                    conversation_id="conv-456",
                    date="2025-01-20",
                    snippet="Let's start with a failing test case",
                ),
            ],
            confidence=0.92,
        ),
        ExtractedPattern(
            name="Code Review Preference",
            description="User prefers detailed code reviews with explanations",
            evidence=[
                PatternEvidence(
                    conversation_id="conv-789",
                    date="2025-01-18",
                    snippet="Can you explain why this approach is better?",
                ),
            ],
            confidence=0.85,
        ),
    ]


@pytest.fixture(autouse=True)
def semantic_components_ready():
    """Mock readiness for semantic components."""
    readiness = Mock()
    readiness.snapshot.return_value = Mock(
        components={
            "metadata": "ready",
            "faiss": "ready",
            "embedder": "ready",
            "embedded_model": "ready",
        }
    )
    with patch("searchat.api.readiness.get_readiness", return_value=readiness):
        yield


def test_extract_patterns_success_ollama(client, mock_patterns):
    """Test successful pattern extraction with ollama provider."""
    config = Mock()

    with patch("searchat.api.routers.patterns.get_config", return_value=config):
        with patch(
            "searchat.api.routers.patterns.extract_patterns", return_value=mock_patterns
        ) as mock_extract:
            resp = client.post(
                "/api/patterns/extract",
                json={
                    "topic": "python development",
                    "max_patterns": 10,
                    "model_provider": "ollama",
                    "model_name": "llama3",
                },
            )

    assert resp.status_code == 200
    data = resp.json()

    assert data["total"] == 2
    assert len(data["patterns"]) == 2

    # Verify first pattern
    p0 = data["patterns"][0]
    assert p0["name"] == "Test-Driven Development"
    assert p0["description"] == "User consistently writes tests before implementation"
    assert p0["confidence"] == 0.92
    assert len(p0["evidence"]) == 2

    # Verify evidence structure
    e0 = p0["evidence"][0]
    assert e0["conversation_id"] == "conv-123"
    assert e0["date"] == "2025-01-15"
    assert e0["snippet"] == "I always write the test first to verify expected behavior"

    # Verify extraction was called correctly
    mock_extract.assert_called_once()
    _, kwargs = mock_extract.call_args
    assert kwargs["topic"] == "python development"
    assert kwargs["max_patterns"] == 10
    assert kwargs["model_provider"] == "ollama"
    assert kwargs["model_name"] == "llama3"


def test_extract_patterns_success_openai(client, mock_patterns):
    """Test successful pattern extraction with openai provider."""
    config = Mock()

    with patch("searchat.api.routers.patterns.get_config", return_value=config):
        with patch(
            "searchat.api.routers.patterns.extract_patterns", return_value=mock_patterns
        ):
            resp = client.post(
                "/api/patterns/extract",
                json={
                    "topic": None,
                    "max_patterns": 5,
                    "model_provider": "openai",
                    "model_name": "gpt-4.1",
                },
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


def test_extract_patterns_success_embedded(client, mock_patterns):
    """Test successful pattern extraction with embedded provider."""
    config = Mock()

    with patch("searchat.api.routers.patterns.get_config", return_value=config):
        with patch(
            "searchat.api.routers.patterns.extract_patterns", return_value=mock_patterns
        ):
            resp = client.post(
                "/api/patterns/extract",
                json={
                    "topic": "api design",
                    "max_patterns": 15,
                    "model_provider": "embedded",
                },
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


def test_extract_patterns_invalid_provider(client):
    """Test pattern extraction with invalid provider."""
    resp = client.post(
        "/api/patterns/extract",
        json={
            "topic": "test",
            "max_patterns": 10,
            "model_provider": "invalid_provider",
        },
    )

    assert resp.status_code == 400
    assert "model_provider must be" in resp.json()["detail"]


def test_extract_patterns_metadata_error(client):
    """Test pattern extraction when metadata component is in error state."""
    readiness = Mock()
    readiness.snapshot.return_value = Mock(
        components={
            "metadata": "error",
            "faiss": "ready",
            "embedder": "ready",
        }
    )

    with patch("searchat.api.readiness.get_readiness", return_value=readiness):
        resp = client.post(
            "/api/patterns/extract",
            json={
                "topic": "test",
                "max_patterns": 10,
                "model_provider": "ollama",
            },
        )

    assert resp.status_code == 500
    assert resp.json()["status"] == "error"


def test_extract_patterns_faiss_not_ready(client):
    """Test pattern extraction when FAISS is not ready."""
    readiness = Mock()
    readiness.snapshot.return_value = Mock(
        components={
            "metadata": "ready",
            "faiss": "idle",
            "embedder": "ready",
        }
    )

    with patch("searchat.api.readiness.get_readiness", return_value=readiness):
        resp = client.post(
            "/api/patterns/extract",
            json={
                "topic": "test",
                "max_patterns": 10,
                "model_provider": "ollama",
            },
        )

    assert resp.status_code == 503
    assert resp.json()["status"] == "warming"


def test_extract_patterns_embedder_not_ready(client):
    """Test pattern extraction when embedder is not ready."""
    readiness = Mock()
    readiness.snapshot.return_value = Mock(
        components={
            "metadata": "ready",
            "faiss": "ready",
            "embedder": "loading",
        }
    )

    with patch("searchat.api.readiness.get_readiness", return_value=readiness):
        resp = client.post(
            "/api/patterns/extract",
            json={
                "topic": "test",
                "max_patterns": 10,
                "model_provider": "ollama",
            },
        )

    assert resp.status_code == 503
    assert resp.json()["status"] == "warming"


def test_extract_patterns_embedded_model_not_ready(client):
    """Test pattern extraction when embedded model is required but not ready."""
    readiness = Mock()
    readiness.snapshot.return_value = Mock(
        components={
            "metadata": "ready",
            "faiss": "ready",
            "embedder": "ready",
            "embedded_model": "idle",
        }
    )

    with patch("searchat.api.readiness.get_readiness", return_value=readiness):
        resp = client.post(
            "/api/patterns/extract",
            json={
                "topic": "test",
                "max_patterns": 10,
                "model_provider": "embedded",
            },
        )

    assert resp.status_code == 503
    assert resp.json()["status"] == "warming"


def test_extract_patterns_service_error(client):
    """Test pattern extraction when service raises an error."""
    config = Mock()

    with patch("searchat.api.routers.patterns.get_config", return_value=config):
        with patch(
            "searchat.api.routers.patterns.extract_patterns",
            side_effect=RuntimeError("Pattern extraction failed"),
        ):
            resp = client.post(
                "/api/patterns/extract",
                json={
                    "topic": "test",
                    "max_patterns": 10,
                    "model_provider": "ollama",
                },
            )

    assert resp.status_code == 500
    assert "Pattern extraction failed" in resp.json()["detail"]


def test_extract_patterns_default_values(client, mock_patterns):
    """Test pattern extraction with default values."""
    config = Mock()

    with patch("searchat.api.routers.patterns.get_config", return_value=config):
        with patch(
            "searchat.api.routers.patterns.extract_patterns", return_value=mock_patterns
        ) as mock_extract:
            resp = client.post(
                "/api/patterns/extract",
                json={},
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2

    # Verify defaults were used
    mock_extract.assert_called_once()
    _, kwargs = mock_extract.call_args
    assert kwargs["topic"] is None
    assert kwargs["max_patterns"] == 10
    assert kwargs["model_provider"] == "ollama"
    assert kwargs["model_name"] is None


def test_extract_patterns_max_patterns_validation(client):
    """Test pattern extraction with invalid max_patterns values."""
    # Test below minimum (0)
    resp = client.post(
        "/api/patterns/extract",
        json={
            "topic": "test",
            "max_patterns": 0,
            "model_provider": "ollama",
        },
    )
    assert resp.status_code == 422

    # Test above maximum (51)
    resp = client.post(
        "/api/patterns/extract",
        json={
            "topic": "test",
            "max_patterns": 51,
            "model_provider": "ollama",
        },
    )
    assert resp.status_code == 422


def test_extract_patterns_empty_results(client):
    """Test pattern extraction when no patterns are found."""
    config = Mock()

    with patch("searchat.api.routers.patterns.get_config", return_value=config):
        with patch("searchat.api.routers.patterns.extract_patterns", return_value=[]):
            resp = client.post(
                "/api/patterns/extract",
                json={
                    "topic": "nonexistent topic",
                    "max_patterns": 10,
                    "model_provider": "ollama",
                },
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["patterns"] == []


def test_extract_patterns_no_evidence(client):
    """Test pattern extraction with patterns that have no evidence."""
    pattern_no_evidence = ExtractedPattern(
        name="Pattern Without Evidence",
        description="This pattern has no supporting evidence",
        evidence=[],
        confidence=0.5,
    )
    config = Mock()

    with patch("searchat.api.routers.patterns.get_config", return_value=config):
        with patch(
            "searchat.api.routers.patterns.extract_patterns",
            return_value=[pattern_no_evidence],
        ):
            resp = client.post(
                "/api/patterns/extract",
                json={
                    "topic": "test",
                    "max_patterns": 10,
                    "model_provider": "ollama",
                },
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["patterns"][0]["evidence"]) == 0
