"""Unit tests for MCP expertise tool functions."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from searchat.expertise.models import ExpertiseRecord, ExpertiseSeverity, ExpertiseType
from searchat.expertise.primer import PrimeFormatter
from searchat.expertise.models import PrimeResult


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_record(
    domain: str = "testing",
    type_: ExpertiseType = ExpertiseType.CONVENTION,
    content: str = "Use type annotations",
) -> ExpertiseRecord:
    return ExpertiseRecord(
        type=type_,
        domain=domain,
        content=content,
        created_at=_utcnow(),
        last_validated=_utcnow(),
    )


def _make_prime_result(records: list[ExpertiseRecord] | None = None) -> PrimeResult:
    recs = records or [_make_record()]
    return PrimeResult(
        expertise=recs,
        token_count=50,
        domains_covered=[r.domain for r in recs],
        records_total=len(recs),
        records_included=len(recs),
        records_filtered_inactive=0,
    )


class TestPrimeExpertise:
    def test_returns_valid_json(self):
        from searchat.mcp.tools import prime_expertise

        prime_result = _make_prime_result()

        with (
            patch("searchat.mcp.tools.resolve_dataset", return_value=MagicMock()),
            patch("searchat.mcp.tools.Config.load", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.query", return_value=[_make_record()]),
            patch(
                "searchat.expertise.primer.ExpertisePrioritizer.prioritize",
                return_value=prime_result,
            ),
        ):
            result = prime_expertise()

        parsed = json.loads(result)
        assert "expertise" in parsed
        assert isinstance(parsed["expertise"], list)

    def test_returns_token_count_and_meta(self):
        from searchat.mcp.tools import prime_expertise

        prime_result = _make_prime_result()

        with (
            patch("searchat.mcp.tools.resolve_dataset", return_value=MagicMock()),
            patch("searchat.mcp.tools.Config.load", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.query", return_value=[_make_record()]),
            patch(
                "searchat.expertise.primer.ExpertisePrioritizer.prioritize",
                return_value=prime_result,
            ),
        ):
            result = prime_expertise(max_tokens=2000)

        parsed = json.loads(result)
        assert "token_count" in parsed
        assert "domains_covered" in parsed
        assert "records_total" in parsed
        assert "records_included" in parsed

    def test_invalid_max_tokens_raises(self):
        from searchat.mcp.tools import prime_expertise

        with pytest.raises(ValueError, match="max_tokens"):
            prime_expertise(max_tokens=50)

    def test_max_tokens_too_large_raises(self):
        from searchat.mcp.tools import prime_expertise

        with pytest.raises(ValueError, match="max_tokens"):
            prime_expertise(max_tokens=99999)

    def test_with_domain_filter(self):
        from searchat.mcp.tools import prime_expertise

        prime_result = _make_prime_result()

        with (
            patch("searchat.mcp.tools.resolve_dataset", return_value=MagicMock()),
            patch("searchat.mcp.tools.Config.load", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.query", return_value=[]) as mock_query,
            patch(
                "searchat.expertise.primer.ExpertisePrioritizer.prioritize",
                return_value=prime_result,
            ),
        ):
            result = prime_expertise(domain="python")

        parsed = json.loads(result)
        assert "expertise" in parsed
        call_args = mock_query.call_args
        assert call_args[0][0].domain == "python"

    def test_with_project_filter(self):
        from searchat.mcp.tools import prime_expertise

        prime_result = _make_prime_result()

        with (
            patch("searchat.mcp.tools.resolve_dataset", return_value=MagicMock()),
            patch("searchat.mcp.tools.Config.load", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.query", return_value=[]) as mock_query,
            patch(
                "searchat.expertise.primer.ExpertisePrioritizer.prioritize",
                return_value=prime_result,
            ),
        ):
            result = prime_expertise(project="my-project")

        parsed = json.loads(result)
        assert "expertise" in parsed
        call_args = mock_query.call_args
        assert call_args[0][0].project == "my-project"

    def test_empty_store_returns_empty_list(self):
        from searchat.mcp.tools import prime_expertise

        empty_result = PrimeResult(
            expertise=[],
            token_count=0,
            domains_covered=[],
            records_total=0,
            records_included=0,
            records_filtered_inactive=0,
        )

        with (
            patch("searchat.mcp.tools.resolve_dataset", return_value=MagicMock()),
            patch("searchat.mcp.tools.Config.load", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.query", return_value=[]),
            patch(
                "searchat.expertise.primer.ExpertisePrioritizer.prioritize",
                return_value=empty_result,
            ),
        ):
            result = prime_expertise()

        parsed = json.loads(result)
        assert parsed["expertise"] == []
        assert parsed["records_total"] == 0


class TestRecordExpertise:
    def test_returns_valid_json_with_id(self):
        from searchat.mcp.tools import record_expertise

        with (
            patch("searchat.mcp.tools.resolve_dataset", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.insert", return_value="exp_abc123"),
        ):
            result = record_expertise(
                type="convention",
                domain="testing",
                content="Always write tests",
            )

        parsed = json.loads(result)
        assert parsed["id"] == "exp_abc123"
        assert parsed["action"] == "created"
        assert parsed["type"] == "convention"
        assert parsed["domain"] == "testing"
        assert parsed["content"] == "Always write tests"

    def test_record_with_severity(self):
        from searchat.mcp.tools import record_expertise

        with (
            patch("searchat.mcp.tools.resolve_dataset", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.insert", return_value="exp_xyz456"),
        ):
            result = record_expertise(
                type="failure",
                domain="infra",
                content="Connection pool exhaustion",
                severity="high",
                resolution="Increase pool size",
            )

        parsed = json.loads(result)
        assert parsed["severity"] == "high"
        assert parsed["id"] == "exp_xyz456"

    def test_record_with_project(self):
        from searchat.mcp.tools import record_expertise

        with (
            patch("searchat.mcp.tools.resolve_dataset", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.insert", return_value="exp_proj123"),
        ):
            result = record_expertise(
                type="decision",
                domain="architecture",
                content="Use microservices",
                project="my-app",
                rationale="Better scalability",
            )

        parsed = json.loads(result)
        assert parsed["project"] == "my-app"

    def test_invalid_type_raises(self):
        from searchat.mcp.tools import record_expertise

        with pytest.raises(ValueError, match="Invalid type"):
            record_expertise(
                type="not_valid",
                domain="testing",
                content="test content",
            )

    def test_invalid_severity_raises(self):
        from searchat.mcp.tools import record_expertise

        with pytest.raises(ValueError, match="Invalid severity"):
            record_expertise(
                type="failure",
                domain="testing",
                content="test content",
                severity="ultra_critical",
            )

    def test_all_expertise_types_accepted(self):
        from searchat.mcp.tools import record_expertise

        for etype in ExpertiseType:
            with (
                patch("searchat.mcp.tools.resolve_dataset", return_value=MagicMock()),
                patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
                patch("searchat.expertise.store.ExpertiseStore.insert", return_value="exp_test"),
            ):
                result = record_expertise(
                    type=etype.value,
                    domain="testing",
                    content=f"Content for {etype.value}",
                )
            parsed = json.loads(result)
            assert parsed["type"] == etype.value

    def test_all_severity_levels_accepted(self):
        from searchat.mcp.tools import record_expertise

        for sev in ExpertiseSeverity:
            with (
                patch("searchat.mcp.tools.resolve_dataset", return_value=MagicMock()),
                patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
                patch("searchat.expertise.store.ExpertiseStore.insert", return_value="exp_sev"),
            ):
                result = record_expertise(
                    type="failure",
                    domain="testing",
                    content="failure content",
                    severity=sev.value,
                )
            parsed = json.loads(result)
            assert parsed["severity"] == sev.value

    def test_returned_json_has_created_at(self):
        from searchat.mcp.tools import record_expertise

        with (
            patch("searchat.mcp.tools.resolve_dataset", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.insert", return_value="exp_ts"),
        ):
            result = record_expertise(
                type="insight",
                domain="general",
                content="Insight content",
            )

        parsed = json.loads(result)
        assert "created_at" in parsed


class TestSearchExpertise:
    def test_returns_valid_json(self):
        from searchat.mcp.tools import search_expertise

        records = [_make_record()]

        with (
            patch("searchat.mcp.tools.resolve_dataset", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.query", return_value=records),
        ):
            result = search_expertise(query="type annotations")

        parsed = json.loads(result)
        assert "results" in parsed
        assert "total" in parsed
        assert "query" in parsed
        assert parsed["query"] == "type annotations"

    def test_results_have_expected_fields(self):
        from searchat.mcp.tools import search_expertise

        records = [_make_record(content="Use type hints")]

        with (
            patch("searchat.mcp.tools.resolve_dataset", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.query", return_value=records),
        ):
            result = search_expertise(query="type hints")

        parsed = json.loads(result)
        assert len(parsed["results"]) == 1
        rec = parsed["results"][0]
        assert "id" in rec
        assert "type" in rec
        assert "domain" in rec
        assert "content" in rec
        assert "confidence" in rec
        assert "is_active" in rec

    def test_empty_results(self):
        from searchat.mcp.tools import search_expertise

        with (
            patch("searchat.mcp.tools.resolve_dataset", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.query", return_value=[]),
        ):
            result = search_expertise(query="nonexistent topic")

        parsed = json.loads(result)
        assert parsed["results"] == []
        assert parsed["total"] == 0

    def test_with_domain_filter(self):
        from searchat.mcp.tools import search_expertise

        with (
            patch("searchat.mcp.tools.resolve_dataset", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.query", return_value=[]) as mock_query,
        ):
            result = search_expertise(query="testing", domain="python")

        parsed = json.loads(result)
        assert parsed["domain"] == "python"
        call_args = mock_query.call_args
        assert call_args[0][0].domain == "python"

    def test_with_type_filter(self):
        from searchat.mcp.tools import search_expertise

        with (
            patch("searchat.mcp.tools.resolve_dataset", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.query", return_value=[]) as mock_query,
        ):
            result = search_expertise(query="patterns", type="pattern")

        parsed = json.loads(result)
        assert parsed["type"] == "pattern"

    def test_invalid_type_raises(self):
        from searchat.mcp.tools import search_expertise

        with pytest.raises(ValueError, match="Invalid type"):
            search_expertise(query="test", type="not_valid")

    def test_limit_out_of_range_raises(self):
        from searchat.mcp.tools import search_expertise

        with pytest.raises(ValueError, match="limit"):
            search_expertise(query="test", limit=0)

        with pytest.raises(ValueError, match="limit"):
            search_expertise(query="test", limit=200)

    def test_limit_applied_to_query(self):
        from searchat.mcp.tools import search_expertise

        with (
            patch("searchat.mcp.tools.resolve_dataset", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.query", return_value=[]) as mock_query,
        ):
            result = search_expertise(query="test", limit=3)

        call_args = mock_query.call_args
        assert call_args[0][0].limit == 3

    def test_multiple_results_returned(self):
        from searchat.mcp.tools import search_expertise

        records = [
            _make_record(domain="testing", content="Record one"),
            _make_record(domain="python", content="Record two"),
            _make_record(domain="infra", content="Record three"),
        ]

        with (
            patch("searchat.mcp.tools.resolve_dataset", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.query", return_value=records),
        ):
            result = search_expertise(query="record")

        parsed = json.loads(result)
        assert parsed["total"] == 3
        assert len(parsed["results"]) == 3
