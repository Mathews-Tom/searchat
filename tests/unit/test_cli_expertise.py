"""Unit tests for `searchat expertise` CLI commands."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from searchat.expertise.models import ExpertiseRecord, ExpertiseSeverity, ExpertiseType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_record(
    domain: str = "testing",
    type_: ExpertiseType = ExpertiseType.CONVENTION,
    content: str = "Always use type hints",
) -> ExpertiseRecord:
    return ExpertiseRecord(
        type=type_,
        domain=domain,
        content=content,
        created_at=_utcnow(),
        last_validated=_utcnow(),
    )


def _mock_config(enabled: bool = True):
    return SimpleNamespace(
        expertise=SimpleNamespace(
            enabled=enabled,
            staleness_threshold=0.85,
            min_age_days=30,
            min_validation_count=0,
            exclude_types=["boundary"],
            pruning_enabled=True,
            pruning_dry_run=False,
        ),
        knowledge_graph=SimpleNamespace(enabled=True),
        performance=SimpleNamespace(memory_limit_mb=512),
    )


class TestExpertiseHelpText:
    def test_expertise_help_exits_zero(self, capsys):
        from searchat.cli.expertise_cmd import run_expertise

        with pytest.raises(SystemExit) as exc_info:
            run_expertise(["--help"])
        assert exc_info.value.code == 0

    def test_expertise_list_help_exits_zero(self, capsys):
        from searchat.cli.expertise_cmd import run_expertise

        with pytest.raises(SystemExit) as exc_info:
            run_expertise(["list", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "--domain" in captured.out

    def test_expertise_prime_help_exits_zero(self, capsys):
        from searchat.cli.expertise_cmd import run_expertise

        with pytest.raises(SystemExit) as exc_info:
            run_expertise(["prime", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "--format" in captured.out

    def test_expertise_status_help_exits_zero(self, capsys):
        from searchat.cli.expertise_cmd import run_expertise

        with pytest.raises(SystemExit) as exc_info:
            run_expertise(["status", "--help"])
        assert exc_info.value.code == 0

    def test_expertise_search_help_exits_zero(self, capsys):
        from searchat.cli.expertise_cmd import run_expertise

        with pytest.raises(SystemExit) as exc_info:
            run_expertise(["search", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "--domain" in captured.out

    def test_expertise_record_help_exits_zero(self, capsys):
        from searchat.cli.expertise_cmd import run_expertise

        with pytest.raises(SystemExit) as exc_info:
            run_expertise(["record", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "--type" in captured.out
        assert "--domain" in captured.out
        assert "--content" in captured.out

    def test_no_subcommand_returns_zero(self, capsys):
        from searchat.cli.expertise_cmd import run_expertise

        result = run_expertise([])
        assert result == 0

    def test_unknown_flag_exits_nonzero(self):
        from searchat.cli.expertise_cmd import run_expertise

        with pytest.raises(SystemExit) as exc_info:
            run_expertise(["--unknown-option"])
        assert exc_info.value.code != 0


class TestExpertiseDisabledConfig:
    def _disabled_config(self):
        return SimpleNamespace(expertise=SimpleNamespace(enabled=False))

    def test_list_disabled_returns_1(self):
        from searchat.cli.expertise_cmd import run_expertise

        with patch("searchat.config.Config.load", return_value=self._disabled_config()):
            result = run_expertise(["list"])
        assert result == 1

    def test_prime_disabled_returns_1(self):
        from searchat.cli.expertise_cmd import run_expertise

        with patch("searchat.config.Config.load", return_value=self._disabled_config()):
            result = run_expertise(["prime"])
        assert result == 1

    def test_status_disabled_returns_1(self):
        from searchat.cli.expertise_cmd import run_expertise

        with patch("searchat.config.Config.load", return_value=self._disabled_config()):
            result = run_expertise(["status"])
        assert result == 1

    def test_search_disabled_returns_1(self):
        from searchat.cli.expertise_cmd import run_expertise

        with patch("searchat.config.Config.load", return_value=self._disabled_config()):
            result = run_expertise(["search", "test query"])
        assert result == 1

    def test_record_disabled_returns_1(self):
        from searchat.cli.expertise_cmd import run_expertise

        with patch("searchat.config.Config.load", return_value=self._disabled_config()):
            result = run_expertise(
                ["record", "--type", "convention", "--domain", "testing", "--content", "test"]
            )
        assert result == 1


class TestExpertiseList:
    def test_list_no_records_returns_zero(self, capsys):
        from searchat.cli.expertise_cmd import run_expertise

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.query", return_value=[]),
        ):
            result = run_expertise(["list"])
        assert result == 0

    def test_list_with_records_shows_table(self, capsys):
        from searchat.cli.expertise_cmd import run_expertise

        records = [_make_record(), _make_record(domain="python", type_=ExpertiseType.FAILURE, content="Watch out for circular imports")]

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.query", return_value=records),
        ):
            result = run_expertise(["list"])
        assert result == 0

    def test_list_with_domain_filter(self, capsys):
        from searchat.cli.expertise_cmd import run_expertise

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.query", return_value=[]) as mock_query,
        ):
            result = run_expertise(["list", "--domain", "python"])

        assert result == 0
        call_args = mock_query.call_args
        assert call_args[0][0].domain == "python"

    def test_list_with_invalid_type_returns_1(self):
        from searchat.cli.expertise_cmd import run_expertise

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
        ):
            result = run_expertise(["list", "--type", "not_a_type"])
        assert result == 1

    def test_list_with_limit(self, capsys):
        from searchat.cli.expertise_cmd import run_expertise

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.query", return_value=[]) as mock_query,
        ):
            result = run_expertise(["list", "--limit", "5"])

        assert result == 0
        call_args = mock_query.call_args
        assert call_args[0][0].limit == 5


class TestExpertiseRecord:
    def test_record_creates_entry(self, capsys):
        from searchat.cli.expertise_cmd import run_expertise

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.insert", return_value="exp_abc123") as mock_insert,
        ):
            result = run_expertise(
                [
                    "record",
                    "--type", "convention",
                    "--domain", "python",
                    "--content", "Use type annotations",
                ]
            )

        assert result == 0
        mock_insert.assert_called_once()
        captured = capsys.readouterr()
        assert "exp_abc123" in captured.out

    def test_record_with_optional_fields(self, capsys):
        from searchat.cli.expertise_cmd import run_expertise

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.insert", return_value="exp_xyz456"),
        ):
            result = run_expertise(
                [
                    "record",
                    "--type", "failure",
                    "--domain", "infra",
                    "--content", "DB connection pooling issue",
                    "--severity", "high",
                    "--resolution", "Set max_pool_size=10",
                    "--tags", "db,pooling",
                ]
            )
        assert result == 0

    def test_record_invalid_type_returns_1(self):
        from searchat.cli.expertise_cmd import run_expertise

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
        ):
            result = run_expertise(
                ["record", "--type", "invalid_type", "--domain", "d", "--content", "c"]
            )
        assert result == 1

    def test_record_invalid_severity_returns_1(self):
        from searchat.cli.expertise_cmd import run_expertise

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
        ):
            result = run_expertise(
                [
                    "record",
                    "--type", "failure",
                    "--domain", "d",
                    "--content", "c",
                    "--severity", "super_critical",
                ]
            )
        assert result == 1

    def test_record_missing_required_args_exits_nonzero(self):
        from searchat.cli.expertise_cmd import run_expertise

        with pytest.raises(SystemExit) as exc_info:
            run_expertise(["record", "--type", "convention"])
        assert exc_info.value.code != 0


class TestExpertisePrime:
    def _make_prime_result(self):
        from searchat.expertise.models import PrimeResult

        return PrimeResult(
            expertise=[_make_record()],
            token_count=20,
            domains_covered=["testing"],
            records_total=1,
            records_included=1,
            records_filtered_inactive=0,
        )

    def test_prime_markdown_format(self, capsys):
        from searchat.cli.expertise_cmd import run_expertise

        prime_result = self._make_prime_result()

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.query", return_value=[_make_record()]),
            patch("searchat.expertise.primer.ExpertisePrioritizer.prioritize", return_value=prime_result),
        ):
            result = run_expertise(["prime", "--format", "markdown"])

        assert result == 0
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_prime_json_format(self, capsys):
        from searchat.cli.expertise_cmd import run_expertise
        import json

        prime_result = self._make_prime_result()

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.query", return_value=[_make_record()]),
            patch("searchat.expertise.primer.ExpertisePrioritizer.prioritize", return_value=prime_result),
        ):
            result = run_expertise(["prime", "--format", "json"])

        assert result == 0
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert "expertise" in parsed

    def test_prime_prompt_format(self, capsys):
        from searchat.cli.expertise_cmd import run_expertise

        prime_result = self._make_prime_result()

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.query", return_value=[_make_record()]),
            patch("searchat.expertise.primer.ExpertisePrioritizer.prioritize", return_value=prime_result),
        ):
            result = run_expertise(["prime", "--format", "prompt"])

        assert result == 0

    def test_prime_empty_store_returns_zero(self, capsys):
        from searchat.cli.expertise_cmd import run_expertise
        from searchat.expertise.models import PrimeResult

        empty_result = PrimeResult(
            expertise=[],
            token_count=0,
            domains_covered=[],
            records_total=0,
            records_included=0,
            records_filtered_inactive=0,
        )

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.query", return_value=[]),
            patch("searchat.expertise.primer.ExpertisePrioritizer.prioritize", return_value=empty_result),
        ):
            result = run_expertise(["prime"])

        assert result == 0


class TestExpertiseStatus:
    def test_status_no_domains_returns_zero(self, capsys):
        from searchat.cli.expertise_cmd import run_expertise

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.list_domains", return_value=[]),
        ):
            result = run_expertise(["status"])
        assert result == 0

    def test_status_with_domains_shows_table(self, capsys):
        from searchat.cli.expertise_cmd import run_expertise

        domains = [{"name": "testing", "description": "", "record_count": 5, "last_updated": "2026-01-01T00:00:00"}]
        stats = {
            "domain": "testing",
            "total_records": 5,
            "active_records": 4,
            "avg_confidence": 0.85,
            "by_type": {"convention": 3, "failure": 1},
        }

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.list_domains", return_value=domains),
            patch("searchat.expertise.store.ExpertiseStore.get_domain_stats", return_value=stats),
        ):
            result = run_expertise(["status"])
        assert result == 0

    def test_status_specific_domain(self, capsys):
        from searchat.cli.expertise_cmd import run_expertise

        stats = {
            "domain": "python",
            "total_records": 10,
            "active_records": 8,
            "avg_confidence": 0.90,
            "by_type": {"convention": 5},
        }

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.get_domain_stats", return_value=stats),
        ):
            result = run_expertise(["status", "--domain", "python"])
        assert result == 0


class TestExpertiseSearch:
    def test_search_no_results(self, capsys):
        from searchat.cli.expertise_cmd import run_expertise

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.query", return_value=[]),
        ):
            result = run_expertise(["search", "missing concept"])
        assert result == 0

    def test_search_with_results(self, capsys):
        from searchat.cli.expertise_cmd import run_expertise

        records = [_make_record(content="Always use type hints in Python")]

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.query", return_value=records),
        ):
            result = run_expertise(["search", "type hints"])
        assert result == 0

    def test_search_passes_query_to_store(self, capsys):
        from searchat.cli.expertise_cmd import run_expertise

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.query", return_value=[]) as mock_query,
        ):
            result = run_expertise(["search", "pytest fixtures"])

        assert result == 0
        call_args = mock_query.call_args
        assert call_args[0][0].q == "pytest fixtures"

    def test_search_with_domain_and_type_filter(self, capsys):
        from searchat.cli.expertise_cmd import run_expertise

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.query", return_value=[]) as mock_query,
        ):
            result = run_expertise(
                ["search", "fixtures", "--domain", "testing", "--type", "pattern"]
            )

        assert result == 0
        call_args = mock_query.call_args
        assert call_args[0][0].domain == "testing"

    def test_search_invalid_type_returns_1(self):
        from searchat.cli.expertise_cmd import run_expertise

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
        ):
            result = run_expertise(["search", "query", "--type", "nonexistent_type"])
        assert result == 1
