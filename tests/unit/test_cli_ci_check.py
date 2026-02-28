"""Unit tests for `searchat ci-check` CLI command."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from searchat.expertise.models import ExpertiseRecord, ExpertiseType
from searchat.expertise.staleness import PruneResult


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_record(domain: str = "testing") -> ExpertiseRecord:
    return ExpertiseRecord(
        type=ExpertiseType.CONVENTION,
        domain=domain,
        content="Test record",
        created_at=_utcnow(),
        last_validated=_utcnow(),
    )


def _mock_config(expertise_enabled: bool = True, kg_enabled: bool = True):
    return SimpleNamespace(
        expertise=SimpleNamespace(
            enabled=expertise_enabled,
            staleness_threshold=0.85,
            min_age_days=30,
            min_validation_count=0,
            exclude_types=["boundary"],
            pruning_enabled=True,
            pruning_dry_run=False,
        ),
        knowledge_graph=SimpleNamespace(enabled=kg_enabled),
        performance=SimpleNamespace(memory_limit_mb=512),
    )


class TestCiCheckHelp:
    def test_help_exits_zero(self, capsys):
        from searchat.cli.ci_check_cmd import run_ci_check

        with pytest.raises(SystemExit) as exc_info:
            run_ci_check(["--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "--fail-on-contradictions" in captured.out
        assert "--fail-on-staleness-threshold" in captured.out

    def test_unknown_flag_exits_nonzero(self):
        from searchat.cli.ci_check_cmd import run_ci_check

        with pytest.raises(SystemExit) as exc_info:
            run_ci_check(["--not-a-flag"])
        assert exc_info.value.code != 0


class TestCiCheckNoChecks:
    def test_no_checks_returns_zero(self, capsys):
        from searchat.cli.ci_check_cmd import run_ci_check

        domains = [{"name": "testing"}]

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.list_domains", return_value=domains),
        ):
            result = run_ci_check([])
        assert result == 0

    def test_disabled_expertise_returns_zero_with_skip(self, capsys):
        from searchat.cli.ci_check_cmd import run_ci_check

        with patch("searchat.config.Config.load", return_value=_mock_config(expertise_enabled=False)):
            result = run_ci_check([])
        assert result == 0
        captured = capsys.readouterr()
        assert "SKIP" in captured.out


class TestCiCheckStaleness:
    def test_no_stale_records_returns_zero(self, capsys):
        from searchat.cli.ci_check_cmd import run_ci_check

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.staleness.StalenessManager.__init__", return_value=None),
            patch(
                "searchat.expertise.staleness.StalenessManager.get_stale_records",
                return_value=[],
            ),
        ):
            result = run_ci_check(["--fail-on-staleness-threshold", "0.8"])
        assert result == 0

    def test_stale_records_above_threshold_returns_1(self, capsys):
        from searchat.cli.ci_check_cmd import run_ci_check

        stale_pairs = [(_make_record(), 0.92)]

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.staleness.StalenessManager.__init__", return_value=None),
            patch(
                "searchat.expertise.staleness.StalenessManager.get_stale_records",
                return_value=stale_pairs,
            ),
        ):
            result = run_ci_check(["--fail-on-staleness-threshold", "0.8"])
        assert result == 1
        captured = capsys.readouterr()
        assert "FAIL" in captured.out

    def test_staleness_threshold_out_of_range_returns_1(self, capsys):
        from searchat.cli.ci_check_cmd import run_ci_check

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
        ):
            result = run_ci_check(["--fail-on-staleness-threshold", "1.5"])
        assert result == 1

    def test_staleness_threshold_negative_returns_1(self, capsys):
        from searchat.cli.ci_check_cmd import run_ci_check

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
        ):
            result = run_ci_check(["--fail-on-staleness-threshold", "-0.1"])
        assert result == 1

    def test_staleness_threshold_zero_is_valid(self, capsys):
        from searchat.cli.ci_check_cmd import run_ci_check

        stale_pairs = [(_make_record(), 0.01)]

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.staleness.StalenessManager.__init__", return_value=None),
            patch(
                "searchat.expertise.staleness.StalenessManager.get_stale_records",
                return_value=stale_pairs,
            ),
        ):
            result = run_ci_check(["--fail-on-staleness-threshold", "0.0"])
        assert result == 1

    def test_staleness_ok_message_printed(self, capsys):
        from searchat.cli.ci_check_cmd import run_ci_check

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.staleness.StalenessManager.__init__", return_value=None),
            patch(
                "searchat.expertise.staleness.StalenessManager.get_stale_records",
                return_value=[],
            ),
        ):
            result = run_ci_check(["--fail-on-staleness-threshold", "0.85"])
        assert result == 0
        captured = capsys.readouterr()
        assert "OK" in captured.out


class TestCiCheckContradictions:
    def test_no_contradictions_returns_zero(self, capsys):
        from searchat.cli.ci_check_cmd import run_ci_check

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.__init__", return_value=None),
            patch(
                "searchat.knowledge_graph.KnowledgeGraphStore.get_contradictions",
                return_value=[],
            ),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.close"),
        ):
            result = run_ci_check(["--fail-on-contradictions"])
        assert result == 0
        captured = capsys.readouterr()
        assert "OK" in captured.out

    def test_unresolved_contradictions_returns_1(self, capsys):
        from searchat.cli.ci_check_cmd import run_ci_check

        fake_edge = MagicMock()
        fake_edge.resolution_id = None

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.__init__", return_value=None),
            patch(
                "searchat.knowledge_graph.KnowledgeGraphStore.get_contradictions",
                return_value=[fake_edge, fake_edge],
            ),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.close"),
        ):
            result = run_ci_check(["--fail-on-contradictions"])
        assert result == 1
        captured = capsys.readouterr()
        assert "FAIL" in captured.out
        assert "2" in captured.out

    def test_kg_disabled_skips_contradiction_check(self, capsys):
        from searchat.cli.ci_check_cmd import run_ci_check

        with (
            patch(
                "searchat.config.Config.load",
                return_value=_mock_config(kg_enabled=False),
            ),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
        ):
            result = run_ci_check(["--fail-on-contradictions"])
        assert result == 0
        captured = capsys.readouterr()
        assert "SKIP" in captured.out

    def test_contradictions_ok_message(self, capsys):
        from searchat.cli.ci_check_cmd import run_ci_check

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.__init__", return_value=None),
            patch(
                "searchat.knowledge_graph.KnowledgeGraphStore.get_contradictions",
                return_value=[],
            ),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.close"),
        ):
            result = run_ci_check(["--fail-on-contradictions"])
        assert result == 0
        captured = capsys.readouterr()
        assert "OK" in captured.out


class TestCiCheckCombined:
    def test_both_checks_pass_returns_zero(self, capsys):
        from searchat.cli.ci_check_cmd import run_ci_check

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.staleness.StalenessManager.__init__", return_value=None),
            patch(
                "searchat.expertise.staleness.StalenessManager.get_stale_records",
                return_value=[],
            ),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.__init__", return_value=None),
            patch(
                "searchat.knowledge_graph.KnowledgeGraphStore.get_contradictions",
                return_value=[],
            ),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.close"),
        ):
            result = run_ci_check(
                ["--fail-on-contradictions", "--fail-on-staleness-threshold", "0.85"]
            )
        assert result == 0

    def test_staleness_fails_contradiction_passes_returns_1(self, capsys):
        from searchat.cli.ci_check_cmd import run_ci_check

        stale_pairs = [(_make_record(), 0.95)]

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.staleness.StalenessManager.__init__", return_value=None),
            patch(
                "searchat.expertise.staleness.StalenessManager.get_stale_records",
                return_value=stale_pairs,
            ),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.__init__", return_value=None),
            patch(
                "searchat.knowledge_graph.KnowledgeGraphStore.get_contradictions",
                return_value=[],
            ),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.close"),
        ):
            result = run_ci_check(
                ["--fail-on-contradictions", "--fail-on-staleness-threshold", "0.85"]
            )
        assert result == 1

    def test_contradictions_fail_staleness_passes_returns_1(self, capsys):
        from searchat.cli.ci_check_cmd import run_ci_check

        fake_edge = MagicMock()
        fake_edge.resolution_id = None

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.staleness.StalenessManager.__init__", return_value=None),
            patch(
                "searchat.expertise.staleness.StalenessManager.get_stale_records",
                return_value=[],
            ),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.__init__", return_value=None),
            patch(
                "searchat.knowledge_graph.KnowledgeGraphStore.get_contradictions",
                return_value=[fake_edge],
            ),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.close"),
        ):
            result = run_ci_check(
                ["--fail-on-contradictions", "--fail-on-staleness-threshold", "0.85"]
            )
        assert result == 1
