"""API tests for the expertise router endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from searchat.api.app import app
from searchat.api.routers.expertise import prime_expertise
from searchat.expertise.models import (
    ExpertiseRecord,
    ExpertiseQuery,
    ExpertiseSeverity,
    ExpertiseType,
)


@pytest.fixture
def client():
    return TestClient(app)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_record(
    type: ExpertiseType = ExpertiseType.CONVENTION,
    domain: str = "testing",
    content: str = "test content",
    **kwargs,
) -> ExpertiseRecord:
    return ExpertiseRecord(type=type, domain=domain, content=content, **kwargs)


def _mock_config(prime_tokens: int = 4000):
    cfg = SimpleNamespace(
        expertise=SimpleNamespace(
            enabled=True,
            default_prime_tokens=prime_tokens,
        )
    )
    return cfg


@pytest.fixture
def mock_store():
    return MagicMock()


@pytest.fixture
def patched_store(mock_store):
    with patch("searchat.api.routers.expertise.get_expertise_store", return_value=mock_store):
        with patch("searchat.api.routers.expertise.get_config", return_value=_mock_config()):
            yield mock_store


class TestCreateExpertise:
    def test_create_expertise(self, client, patched_store):
        patched_store.insert.return_value = "exp_abc123"

        resp = client.post(
            "/api/expertise",
            json={
                "type": "convention",
                "domain": "coding",
                "content": "use snake_case for variables",
            },
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["action"] == "created"
        assert data["record"]["type"] == "convention"
        assert data["record"]["domain"] == "coding"
        assert data["record"]["content"] == "use snake_case for variables"

    def test_create_expertise_invalid_type(self, client, patched_store):
        resp = client.post(
            "/api/expertise",
            json={
                "type": "invalid_type",
                "domain": "coding",
                "content": "some content",
            },
        )

        assert resp.status_code == 422

    def test_create_expertise_missing_required_fields(self, client, patched_store):
        resp = client.post(
            "/api/expertise",
            json={"type": "convention"},
        )

        assert resp.status_code == 422

    def test_create_expertise_with_severity(self, client, patched_store):
        patched_store.insert.return_value = "exp_xyz"

        resp = client.post(
            "/api/expertise",
            json={
                "type": "failure",
                "domain": "auth",
                "content": "token expiry not handled",
                "severity": "critical",
                "resolution": "add refresh token logic",
            },
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["record"]["severity"] == "critical"
        assert data["record"]["resolution"] == "add refresh token logic"


class TestListExpertise:
    def test_list_expertise(self, client, patched_store):
        record = _make_record(type=ExpertiseType.CONVENTION, domain="coding", content="use type hints")
        patched_store.query.return_value = [record]

        resp = client.get("/api/expertise")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["results"]) == 1
        assert data["results"][0]["content"] == "use type hints"

    def test_list_expertise_domain_filter(self, client, patched_store):
        record_a = _make_record(domain="auth", content="use jwt")
        record_b = _make_record(domain="db", content="use indexes")
        patched_store.query.side_effect = lambda q: [record_a] if q.domain == "auth" else [record_b]

        resp = client.get("/api/expertise?domain=auth")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["results"][0]["domain"] == "auth"
        assert data["filters"]["domain"] == "auth"

    def test_list_expertise_type_filter(self, client, patched_store):
        record = _make_record(type=ExpertiseType.BOUNDARY, content="no direct db access from UI")
        patched_store.query.return_value = [record]

        resp = client.get("/api/expertise?type=boundary")

        assert resp.status_code == 200
        data = resp.json()
        assert data["results"][0]["type"] == "boundary"

    def test_list_expertise_empty(self, client, patched_store):
        patched_store.query.return_value = []

        resp = client.get("/api/expertise")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["results"] == []


class TestGetExpertise:
    def test_get_expertise_by_id(self, client, patched_store):
        record = _make_record(content="specific record")
        patched_store.get.return_value = record

        resp = client.get(f"/api/expertise/status")
        # status is a fixed path, use a valid record id path
        resp = client.get(f"/api/expertise/{record.id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == record.id
        assert data["content"] == "specific record"

    def test_get_expertise_not_found(self, client, patched_store):
        patched_store.get.return_value = None

        resp = client.get("/api/expertise/nonexistent_id")

        assert resp.status_code == 404


class TestUpdateExpertise:
    def test_update_expertise(self, client, patched_store):
        original = _make_record(content="original content")
        updated = _make_record(content="updated content")
        updated.id = original.id

        patched_store.get.side_effect = [original, updated]

        resp = client.patch(
            f"/api/expertise/{original.id}",
            json={"content": "updated content"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "updated content"
        patched_store.update.assert_called_once_with(original.id, content="updated content")

    def test_update_expertise_not_found(self, client, patched_store):
        patched_store.get.return_value = None

        resp = client.patch(
            "/api/expertise/nonexistent",
            json={"content": "new content"},
        )

        assert resp.status_code == 404


class TestDeleteExpertise:
    def test_delete_expertise(self, client, patched_store):
        record = _make_record(content="to be deleted")
        patched_store.get.return_value = record

        resp = client.delete(f"/api/expertise/{record.id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "deleted"
        assert data["id"] == record.id
        patched_store.soft_delete.assert_called_once_with(record.id)

    def test_delete_expertise_not_found(self, client, patched_store):
        patched_store.get.return_value = None

        resp = client.delete("/api/expertise/nonexistent")

        assert resp.status_code == 404


class TestValidateExpertise:
    def test_validate_expertise(self, client, patched_store):
        record = _make_record(content="to validate", validation_count=1)
        validated = _make_record(content="to validate", validation_count=2)
        validated.id = record.id

        patched_store.get.side_effect = [record, validated]

        resp = client.post(f"/api/expertise/{record.id}/validate")

        assert resp.status_code == 200
        data = resp.json()
        assert data["validation_count"] == 2
        patched_store.validate_record.assert_called_once_with(record.id)

    def test_validate_expertise_not_found(self, client, patched_store):
        patched_store.get.return_value = None

        resp = client.post("/api/expertise/nonexistent/validate")

        assert resp.status_code == 404


class TestDomains:
    def test_list_domains(self, client, patched_store):
        patched_store.list_domains.return_value = [
            {
                "name": "coding",
                "description": "Coding conventions",
                "record_count": 5,
                "last_updated": _utcnow().isoformat(),
            }
        ]

        resp = client.get("/api/expertise/domains")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "coding"
        assert data[0]["record_count"] == 5

    def test_create_domain(self, client, patched_store):
        resp = client.post(
            "/api/expertise/domains",
            json={"name": "infra", "description": "Infrastructure patterns"},
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "infra"
        assert data["description"] == "Infrastructure patterns"
        assert data["record_count"] == 0
        patched_store.create_domain.assert_called_once_with("infra", "Infrastructure patterns")

    def test_list_domains_empty(self, client, patched_store):
        patched_store.list_domains.return_value = []

        resp = client.get("/api/expertise/domains")

        assert resp.status_code == 200
        assert resp.json() == []


class TestExpertiseStatus:
    def test_expertise_status(self, client, patched_store):
        records = [
            _make_record(domain="coding", is_active=True),
            _make_record(domain="auth", is_active=False),
        ]
        patched_store.query.return_value = records
        patched_store.get_domain_stats.return_value = {
            "domain": "coding",
            "total_records": 1,
            "active_records": 1,
        }

        resp = client.get("/api/expertise/status")

        assert resp.status_code == 200
        data = resp.json()
        assert "total_records" in data
        assert "active_records" in data
        assert "domains" in data
        assert isinstance(data["domains"], list)


class TestPrimeEndpoint:
    """Tests for the prime endpoint.

    NOTE: The /prime GET route is defined after /{record_id} in the router, so
    GET /api/expertise/prime is matched by the /{record_id} handler with record_id="prime".
    When the store returns None for id "prime", the endpoint returns 404. The prime
    endpoint function itself is tested via the prioritizer unit tests and direct invocation.
    """

    def test_prime_route_reachable_via_http(self, client, patched_store):
        patched_store.query.return_value = []

        resp = client.get("/api/expertise/prime")

        assert resp.status_code == 200

    def test_prime_json_via_direct_invocation(self, patched_store):
        """Test prime endpoint logic directly via the router function."""
        record = _make_record(
            type=ExpertiseType.BOUNDARY, content="never delete production data"
        )
        patched_store.query.return_value = [record]

        result = prime_expertise(project=None, domain=None, max_tokens=None, format="json")

        assert "expertise" in result
        assert "token_count" in result
        assert "domains_covered" in result
        assert "records_total" in result
        assert "records_included" in result

    def test_prime_markdown_via_direct_invocation(self, patched_store):
        record = _make_record(
            type=ExpertiseType.CONVENTION, content="use snake_case"
        )
        patched_store.query.return_value = [record]

        result = prime_expertise(project=None, domain=None, max_tokens=None, format="markdown")

        assert "content" in result
        assert "## Project Expertise" in result["content"]

    def test_prime_prompt_via_direct_invocation(self, patched_store):
        record = _make_record(
            type=ExpertiseType.PATTERN, content="use factory pattern"
        )
        patched_store.query.return_value = [record]

        result = prime_expertise(project=None, domain=None, max_tokens=None, format="prompt")

        assert "content" in result
        assert "[PATTERN]" in result["content"]

    def test_prime_with_max_tokens_via_direct_invocation(self, patched_store):
        records = [
            _make_record(
                type=ExpertiseType.BOUNDARY,
                content=" ".join(["word"] * 80),  # ~104 tokens
                domain=f"d{i}",
            )
            for i in range(5)
        ]
        patched_store.query.return_value = records

        result = prime_expertise(project=None, domain=None, max_tokens=120, format="json")

        assert result["token_count"] <= 120

    def test_prime_with_domain_filter_via_direct_invocation(self, patched_store):
        record = _make_record(domain="auth", content="validate tokens")
        patched_store.query.return_value = [record]

        prime_expertise(project=None, domain="auth", max_tokens=None, format="json")

        call_args = patched_store.query.call_args[0][0]
        assert call_args.domain == "auth"

    def test_prime_empty_store_via_direct_invocation(self, patched_store):
        patched_store.query.return_value = []

        result = prime_expertise(project=None, domain=None, max_tokens=None, format="json")

        assert result["records_total"] == 0
        assert result["records_included"] == 0
        assert result["expertise"] == []
