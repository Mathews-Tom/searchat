"""Unit tests for `searchat contradictions` CLI command."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from searchat.expertise.models import ExpertiseRecord, ExpertiseType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_record(domain: str = "testing", content: str = "Some expertise") -> ExpertiseRecord:
    return ExpertiseRecord(
        type=ExpertiseType.CONVENTION,
        domain=domain,
        content=content,
        created_at=_utcnow(),
        last_validated=_utcnow(),
    )


def _mock_edge(edge_id: str = "edge_001", resolved: bool = False):
    edge = MagicMock()
    edge.id = edge_id
    edge.source_id = "rec_a"
    edge.target_id = "rec_b"
    edge.resolution_id = "res_123" if resolved else None
    return edge


def _mock_config(kg_enabled: bool = True):
    return SimpleNamespace(
        knowledge_graph=SimpleNamespace(enabled=kg_enabled),
        expertise=SimpleNamespace(enabled=True),
        performance=SimpleNamespace(memory_limit_mb=512),
    )


class TestContradictionsHelp:
    def test_help_exits_zero(self, capsys):
        from searchat.cli.contradictions_cmd import run_contradictions

        with pytest.raises(SystemExit) as exc_info:
            run_contradictions(["--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "--domain" in captured.out
        assert "--unresolved-only" in captured.out

    def test_unknown_flag_exits_nonzero(self):
        from searchat.cli.contradictions_cmd import run_contradictions

        with pytest.raises(SystemExit) as exc_info:
            run_contradictions(["--not-a-flag"])
        assert exc_info.value.code != 0


class TestContradictionsDisabled:
    def test_kg_disabled_returns_1(self, capsys):
        from searchat.cli.contradictions_cmd import run_contradictions

        with patch("searchat.config.Config.load", return_value=_mock_config(kg_enabled=False)):
            result = run_contradictions([])
        assert result == 1


class TestContradictionsOutput:
    def test_no_contradictions_returns_zero(self, capsys):
        from searchat.cli.contradictions_cmd import run_contradictions

        kg_store = MagicMock()
        kg_store.get_contradictions.return_value = []

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.__init__", return_value=None),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.get_contradictions", return_value=[]),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.close"),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
        ):
            result = run_contradictions([])
        assert result == 0

    def test_with_open_contradictions_shows_table(self, capsys):
        from searchat.cli.contradictions_cmd import run_contradictions

        edge = _mock_edge(resolved=False)
        rec_a = _make_record(content="Always prefer X")
        rec_b = _make_record(content="Always prefer Y")

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.__init__", return_value=None),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.get_contradictions", return_value=[edge]),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.close"),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.get", side_effect=[rec_a, rec_b]),
        ):
            result = run_contradictions([])
        assert result == 0

    def test_with_resolved_contradictions(self, capsys):
        from searchat.cli.contradictions_cmd import run_contradictions

        edge = _mock_edge(resolved=True)
        rec_a = _make_record(content="Resolved A")
        rec_b = _make_record(content="Resolved B")

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.__init__", return_value=None),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.get_contradictions", return_value=[edge]),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.close"),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.get", side_effect=[rec_a, rec_b]),
        ):
            result = run_contradictions([])
        assert result == 0

    def test_unresolved_only_flag_passed_to_store(self, capsys):
        from searchat.cli.contradictions_cmd import run_contradictions

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.__init__", return_value=None),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.get_contradictions", return_value=[]) as mock_get,
            patch("searchat.knowledge_graph.KnowledgeGraphStore.close"),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
        ):
            result = run_contradictions(["--unresolved-only"])

        assert result == 0
        mock_get.assert_called_once_with(unresolved_only=True)

    def test_domain_filter_narrows_results(self, capsys):
        from searchat.cli.contradictions_cmd import run_contradictions

        edge = _mock_edge()
        rec_a = _make_record(domain="python")
        rec_b = _make_record(domain="other")

        # get() is called twice for domain filtering and again for display (2 calls in filter, 2 in display)
        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.__init__", return_value=None),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.get_contradictions", return_value=[edge]),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.close"),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.get", side_effect=[rec_a, rec_b, rec_a, rec_b]),
        ):
            result = run_contradictions(["--domain", "python"])
        assert result == 0

    def test_domain_filter_excludes_non_matching(self, capsys):
        from searchat.cli.contradictions_cmd import run_contradictions

        edge = _mock_edge()
        rec_a = _make_record(domain="other")
        rec_b = _make_record(domain="other")

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.__init__", return_value=None),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.get_contradictions", return_value=[edge]),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.close"),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.get", side_effect=[rec_a, rec_b]),
        ):
            result = run_contradictions(["--domain", "python"])
        assert result == 0

    def test_limit_applied(self, capsys):
        from searchat.cli.contradictions_cmd import run_contradictions

        edges = [_mock_edge(f"edge_{i}") for i in range(10)]

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.__init__", return_value=None),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.get_contradictions", return_value=edges),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.close"),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.get", return_value=_make_record()),
        ):
            result = run_contradictions(["--limit", "3"])
        assert result == 0

    def test_deleted_records_show_as_deleted(self, capsys):
        from searchat.cli.contradictions_cmd import run_contradictions

        edge = _mock_edge()

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch("searchat.config.PathResolver.get_shared_search_dir", return_value=MagicMock()),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.__init__", return_value=None),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.get_contradictions", return_value=[edge]),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.close"),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.get", return_value=None),
        ):
            result = run_contradictions([])
        assert result == 0
