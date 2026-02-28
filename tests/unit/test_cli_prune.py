"""Unit tests for searchat prune and searchat validate CLI commands."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from searchat.expertise.models import ExpertiseRecord, ExpertiseType
from searchat.expertise.staleness import PruneResult


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_old_record(domain: str = "testing") -> ExpertiseRecord:
    old_date = _utcnow() - timedelta(days=200)
    return ExpertiseRecord(
        type=ExpertiseType.INSIGHT,
        domain=domain,
        content="old insight",
        last_validated=old_date,
        created_at=old_date - timedelta(days=10),
    )


def _mock_config(staleness_threshold: float = 0.85):
    return SimpleNamespace(
        expertise=SimpleNamespace(
            enabled=True,
            staleness_threshold=staleness_threshold,
            min_age_days=30,
            min_validation_count=0,
            exclude_types=["boundary"],
            pruning_enabled=True,
            pruning_dry_run=False,
        ),
        performance=SimpleNamespace(memory_limit_mb=512),
    )


class TestPruneHelpText:
    def test_prune_help_text(self, capsys):
        from searchat.cli.prune import run_prune

        with pytest.raises(SystemExit) as exc_info:
            run_prune(["--help"])

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "prune" in captured.out.lower()
        assert "--threshold" in captured.out
        assert "--dry-run" in captured.out or "--force" in captured.out

    def test_prune_unknown_arg_exits_nonzero(self):
        from searchat.cli.prune import run_prune

        with pytest.raises(SystemExit) as exc_info:
            run_prune(["--unknown-flag"])

        assert exc_info.value.code != 0


class TestPruneDryRun:
    def test_prune_dry_run_shows_records(self, capsys):
        from searchat.cli.prune import run_prune

        old_rec = _make_old_record()
        mock_manager = MagicMock()
        mock_manager.get_stale_records.return_value = [(old_rec, 0.92)]

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.staleness.StalenessManager.__init__", return_value=None),
            patch("searchat.expertise.staleness.StalenessManager.get_stale_records", return_value=[(old_rec, 0.92)]),
        ):
            result = run_prune(["--dry-run"])

        assert result == 0

    def test_prune_dry_run_no_stale_records(self, capsys):
        from searchat.cli.prune import run_prune

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.staleness.StalenessManager.__init__", return_value=None),
            patch("searchat.expertise.staleness.StalenessManager.get_stale_records", return_value=[]),
        ):
            result = run_prune(["--dry-run"])

        assert result == 0

    def test_prune_disabled_config_returns_error(self):
        from searchat.cli.prune import run_prune

        disabled_config = SimpleNamespace(
            expertise=SimpleNamespace(enabled=False)
        )

        with patch("searchat.config.Config.load", return_value=disabled_config):
            result = run_prune([])

        assert result == 1

    def test_prune_force_executes_without_prompt(self, capsys):
        from searchat.cli.prune import run_prune

        old_rec = _make_old_record()
        mock_result = PruneResult(
            pruned=[old_rec], skipped=[], total_evaluated=1, dry_run=False
        )

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.staleness.StalenessManager.__init__", return_value=None),
            patch("searchat.expertise.staleness.StalenessManager.get_stale_records", return_value=[(old_rec, 0.92)]),
            patch("searchat.expertise.staleness.StalenessManager.prune", return_value=mock_result),
        ):
            result = run_prune(["--force"])

        assert result == 0


class TestValidateHelpText:
    def test_validate_help_text(self, capsys):
        from searchat.cli.validate_cmd import run_validate

        with pytest.raises(SystemExit) as exc_info:
            run_validate(["--help"])

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "validate" in captured.out.lower()
        assert "--domain" in captured.out
        assert "--project" in captured.out

    def test_validate_disabled_config_returns_error(self):
        from searchat.cli.validate_cmd import run_validate

        disabled_config = SimpleNamespace(
            expertise=SimpleNamespace(enabled=False)
        )

        with patch("searchat.config.Config.load", return_value=disabled_config):
            result = run_validate([])

        assert result == 1
