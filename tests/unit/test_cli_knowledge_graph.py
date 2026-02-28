"""Unit tests for `searchat graph` CLI commands."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from searchat.knowledge_graph.models import EdgeType, KnowledgeEdge, ResolutionStrategy


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_edge(
    source_id: str = "rec_aaa",
    target_id: str = "rec_bbb",
    edge_type: EdgeType = EdgeType.CONTRADICTS,
    resolution_id: str | None = None,
) -> KnowledgeEdge:
    return KnowledgeEdge(
        source_id=source_id,
        target_id=target_id,
        edge_type=edge_type,
        metadata=None,
        created_by=None,
        resolution_id=resolution_id,
    )


def _mock_config(kg_enabled: bool = True):
    return SimpleNamespace(
        knowledge_graph=SimpleNamespace(
            enabled=kg_enabled,
            similarity_threshold=0.75,
            contradiction_threshold=0.70,
            nli_model="cross-encoder/nli-deberta-v3-xsmall",
        ),
        expertise=SimpleNamespace(enabled=True),
        performance=SimpleNamespace(memory_limit_mb=512),
    )


def _mock_expertise_record(
    record_id: str = "rec_1",
    content: str = "test content",
    domain: str = "testing",
):
    rec = MagicMock()
    rec.id = record_id
    rec.content = content
    rec.domain = domain
    return rec


# ---------------------------------------------------------------------------
# Help text
# ---------------------------------------------------------------------------


class TestHelpText:
    def test_graph_help_exits_zero(self, capsys):
        from searchat.cli.knowledge_graph_cmd import run_graph

        with pytest.raises(SystemExit) as exc_info:
            run_graph(["--help"])

        assert exc_info.value.code == 0

    def test_subcommand_help_exits_zero(self, capsys):
        from searchat.cli.knowledge_graph_cmd import run_graph

        with pytest.raises(SystemExit) as exc_info:
            run_graph(["stats", "--help"])

        assert exc_info.value.code == 0

    def test_unknown_subcommand_exits_nonzero(self):
        from searchat.cli.knowledge_graph_cmd import run_graph

        with pytest.raises(SystemExit) as exc_info:
            run_graph(["unknown-subcommand"])

        assert exc_info.value.code != 0

    def test_no_args_exits_zero(self, capsys):
        from searchat.cli.knowledge_graph_cmd import run_graph

        result = run_graph([])

        assert result == 0
        captured = capsys.readouterr()
        assert "graph" in captured.out.lower()


# ---------------------------------------------------------------------------
# graph stats
# ---------------------------------------------------------------------------


class TestStats:
    def test_stats_disabled_config_returns_error(self):
        from searchat.cli.knowledge_graph_cmd import run_graph

        with patch("searchat.config.Config.load", return_value=_mock_config(kg_enabled=False)):
            result = run_graph(["stats"])

        assert result == 1

    def test_stats_shows_node_and_edge_counts(self, capsys):
        from searchat.cli.knowledge_graph_cmd import run_graph
        from searchat.expertise.models import ExpertiseQuery

        mock_rec = _mock_expertise_record()

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch(
                "searchat.config.PathResolver.get_shared_search_dir",
                return_value=MagicMock(),
            ),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.__init__", return_value=None),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.get_contradictions", return_value=[]),
            patch(
                "searchat.knowledge_graph.KnowledgeGraphStore.get_edges_for_record",
                return_value=[],
            ),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.close", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch(
                "searchat.expertise.store.ExpertiseStore.query",
                return_value=[mock_rec],
            ),
        ):
            result = run_graph(["stats"])

        assert result == 0
        captured = capsys.readouterr()
        assert "Knowledge Graph" in captured.out
        assert "Nodes" in captured.out or "nodes" in captured.out.lower()

    def test_stats_zero_records(self, capsys):
        from searchat.cli.knowledge_graph_cmd import run_graph

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch(
                "searchat.config.PathResolver.get_shared_search_dir",
                return_value=MagicMock(),
            ),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.__init__", return_value=None),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.get_contradictions", return_value=[]),
            patch(
                "searchat.knowledge_graph.KnowledgeGraphStore.get_edges_for_record",
                return_value=[],
            ),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.close", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.query", return_value=[]),
        ):
            result = run_graph(["stats"])

        assert result == 0


# ---------------------------------------------------------------------------
# graph contradictions
# ---------------------------------------------------------------------------


class TestContradictions:
    def test_contradictions_disabled_config_returns_error(self):
        from searchat.cli.knowledge_graph_cmd import run_graph

        with patch("searchat.config.Config.load", return_value=_mock_config(kg_enabled=False)):
            result = run_graph(["contradictions"])

        assert result == 1

    def test_contradictions_no_results(self, capsys):
        from searchat.cli.knowledge_graph_cmd import run_graph

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch(
                "searchat.config.PathResolver.get_shared_search_dir",
                return_value=MagicMock(),
            ),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.__init__", return_value=None),
            patch(
                "searchat.knowledge_graph.KnowledgeGraphStore.get_contradictions",
                return_value=[],
            ),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.close", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
        ):
            result = run_graph(["contradictions"])

        assert result == 0
        captured = capsys.readouterr()
        assert "No" in captured.out

    def test_contradictions_shows_edges(self, capsys):
        from searchat.cli.knowledge_graph_cmd import run_graph

        edge = _make_edge()
        rec_a = _mock_expertise_record("rec_aaa", "content A")
        rec_b = _mock_expertise_record("rec_bbb", "content B")

        def _get_rec(rid):
            return rec_a if rid == "rec_aaa" else rec_b

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch(
                "searchat.config.PathResolver.get_shared_search_dir",
                return_value=MagicMock(),
            ),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.__init__", return_value=None),
            patch(
                "searchat.knowledge_graph.KnowledgeGraphStore.get_contradictions",
                return_value=[edge],
            ),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.close", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.get", side_effect=_get_rec),
        ):
            result = run_graph(["contradictions"])

        assert result == 0
        captured = capsys.readouterr()
        assert edge.id in captured.out
        assert "content A" in captured.out

    def test_contradictions_unresolved_only_flag(self, capsys):
        from searchat.cli.knowledge_graph_cmd import run_graph

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch(
                "searchat.config.PathResolver.get_shared_search_dir",
                return_value=MagicMock(),
            ),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.__init__", return_value=None),
            patch(
                "searchat.knowledge_graph.KnowledgeGraphStore.get_contradictions",
                return_value=[],
            ) as mock_get,
            patch("searchat.knowledge_graph.KnowledgeGraphStore.close", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
        ):
            result = run_graph(["contradictions", "--unresolved-only"])

        assert result == 0
        mock_get.assert_called_once_with(unresolved_only=True)

    def test_contradictions_domain_filter(self, capsys):
        from searchat.cli.knowledge_graph_cmd import run_graph

        edge_auth = _make_edge(source_id="rec_auth", target_id="rec_auth2")
        edge_db = _make_edge(source_id="rec_db", target_id="rec_db2")
        rec_auth = _mock_expertise_record("rec_auth", domain="auth")
        rec_db = _mock_expertise_record("rec_db", domain="db")

        def _get_rec(rid):
            if "auth" in rid:
                return rec_auth
            return rec_db

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch(
                "searchat.config.PathResolver.get_shared_search_dir",
                return_value=MagicMock(),
            ),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.__init__", return_value=None),
            patch(
                "searchat.knowledge_graph.KnowledgeGraphStore.get_contradictions",
                return_value=[edge_auth, edge_db],
            ),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.close", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.get", side_effect=_get_rec),
        ):
            result = run_graph(["contradictions", "--domain", "auth"])

        assert result == 0
        captured = capsys.readouterr()
        assert edge_auth.id in captured.out
        assert edge_db.id not in captured.out


# ---------------------------------------------------------------------------
# graph resolve
# ---------------------------------------------------------------------------


class TestResolve:
    def _make_resolution_result(self, strategy=ResolutionStrategy.DISMISS):
        from searchat.knowledge_graph.models import ResolutionResult

        return ResolutionResult(
            strategy=strategy,
            edge_id="edge_abc",
            created_edges=[],
            deactivated_records=[],
            new_record_id=None,
            note="Resolved.",
            resolved_at=_utcnow(),
        )

    def test_resolve_disabled_config_returns_error(self):
        from searchat.cli.knowledge_graph_cmd import run_graph

        with patch("searchat.config.Config.load", return_value=_mock_config(kg_enabled=False)):
            result = run_graph(["resolve", "edge_abc", "dismiss"])

        assert result == 1

    def test_resolve_edge_not_found_returns_error(self):
        from searchat.cli.knowledge_graph_cmd import run_graph

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch(
                "searchat.config.PathResolver.get_shared_search_dir",
                return_value=MagicMock(),
            ),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.__init__", return_value=None),
            patch(
                "searchat.knowledge_graph.KnowledgeGraphStore.get_edge",
                return_value=None,
            ),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.close", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
        ):
            result = run_graph(
                ["resolve", "nonexistent", "dismiss", "--params", '{"reason": "x"}']
            )

        assert result == 1

    def test_resolve_non_contradiction_edge_returns_error(self):
        from searchat.cli.knowledge_graph_cmd import run_graph

        edge = _make_edge(edge_type=EdgeType.SUPERSEDES)

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch(
                "searchat.config.PathResolver.get_shared_search_dir",
                return_value=MagicMock(),
            ),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.__init__", return_value=None),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.get_edge", return_value=edge),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.close", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
        ):
            result = run_graph(
                ["resolve", edge.id, "dismiss", "--params", '{"reason": "x"}']
            )

        assert result == 1

    def test_resolve_dismiss_succeeds(self, capsys):
        from searchat.cli.knowledge_graph_cmd import run_graph
        from searchat.knowledge_graph.resolver import ResolutionEngine

        edge = _make_edge()
        result = self._make_resolution_result()

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch(
                "searchat.config.PathResolver.get_shared_search_dir",
                return_value=MagicMock(),
            ),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.__init__", return_value=None),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.get_edge", return_value=edge),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.close", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch.object(ResolutionEngine, "__init__", return_value=None),
            patch.object(ResolutionEngine, "dismiss", return_value=result),
        ):
            exit_code = run_graph(
                [
                    "resolve",
                    edge.id,
                    "dismiss",
                    "--params",
                    '{"reason": "Not real"}',
                ]
            )

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Resolution applied" in captured.out
        assert result.resolution_id in captured.out

    def test_resolve_invalid_json_params_returns_error(self):
        from searchat.cli.knowledge_graph_cmd import run_graph

        with patch("searchat.config.Config.load", return_value=_mock_config()):
            result = run_graph(["resolve", "edge_abc", "dismiss", "--params", "not-json"])

        assert result == 1

    def test_resolve_missing_required_param_returns_error(self):
        from searchat.cli.knowledge_graph_cmd import run_graph

        edge = _make_edge()

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch(
                "searchat.config.PathResolver.get_shared_search_dir",
                return_value=MagicMock(),
            ),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.__init__", return_value=None),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.get_edge", return_value=edge),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.close", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
        ):
            # dismiss requires "reason" in params
            result = run_graph(["resolve", edge.id, "dismiss", "--params", "{}"])

        assert result == 1


# ---------------------------------------------------------------------------
# graph lineage
# ---------------------------------------------------------------------------


class TestLineage:
    def test_lineage_disabled_config_returns_error(self):
        from searchat.cli.knowledge_graph_cmd import run_graph

        with patch("searchat.config.Config.load", return_value=_mock_config(kg_enabled=False)):
            result = run_graph(["lineage", "rec_123"])

        assert result == 1

    def test_lineage_missing_record_returns_error(self):
        from searchat.cli.knowledge_graph_cmd import run_graph

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch(
                "searchat.config.PathResolver.get_shared_search_dir",
                return_value=MagicMock(),
            ),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.__init__", return_value=None),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.close", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.get", return_value=None),
        ):
            result = run_graph(["lineage", "nonexistent"])

        assert result == 1

    def test_lineage_shows_conversations(self, capsys):
        from searchat.cli.knowledge_graph_cmd import run_graph
        from searchat.knowledge_graph.provenance import ProvenanceTracker

        rec = _mock_expertise_record("rec_1", "some expertise content")

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch(
                "searchat.config.PathResolver.get_shared_search_dir",
                return_value=MagicMock(),
            ),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.__init__", return_value=None),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.close", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.get", return_value=rec),
            patch.object(ProvenanceTracker, "__init__", return_value=None),
            patch.object(
                ProvenanceTracker,
                "get_full_lineage",
                return_value={
                    "conversations": ["conv_abc", "conv_def"],
                    "derived_records": [],
                },
            ),
        ):
            result = run_graph(["lineage", "rec_1"])

        assert result == 0
        captured = capsys.readouterr()
        assert "conv_abc" in captured.out
        assert "conv_def" in captured.out

    def test_lineage_no_conversations(self, capsys):
        from searchat.cli.knowledge_graph_cmd import run_graph
        from searchat.knowledge_graph.provenance import ProvenanceTracker

        rec = _mock_expertise_record("rec_1")

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch(
                "searchat.config.PathResolver.get_shared_search_dir",
                return_value=MagicMock(),
            ),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.__init__", return_value=None),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.close", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.get", return_value=rec),
            patch.object(ProvenanceTracker, "__init__", return_value=None),
            patch.object(
                ProvenanceTracker,
                "get_full_lineage",
                return_value={"conversations": [], "derived_records": []},
            ),
        ):
            result = run_graph(["lineage", "rec_1"])

        assert result == 0
        captured = capsys.readouterr()
        assert "No source conversations" in captured.out

    def test_lineage_shows_derived_records(self, capsys):
        from searchat.cli.knowledge_graph_cmd import run_graph
        from searchat.knowledge_graph.provenance import ProvenanceTracker

        rec = _mock_expertise_record("rec_1")
        derived_rec = _mock_expertise_record("rec_derived", "derived content")

        def _get_rec(rid):
            if rid == "rec_1":
                return rec
            if rid == "rec_derived":
                return derived_rec
            return None

        with (
            patch("searchat.config.Config.load", return_value=_mock_config()),
            patch(
                "searchat.config.PathResolver.get_shared_search_dir",
                return_value=MagicMock(),
            ),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.__init__", return_value=None),
            patch("searchat.knowledge_graph.KnowledgeGraphStore.close", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.__init__", return_value=None),
            patch("searchat.expertise.store.ExpertiseStore.get", side_effect=_get_rec),
            patch.object(ProvenanceTracker, "__init__", return_value=None),
            patch.object(
                ProvenanceTracker,
                "get_full_lineage",
                return_value={
                    "conversations": ["conv_abc"],
                    "derived_records": ["rec_derived"],
                },
            ),
        ):
            result = run_graph(["lineage", "rec_1"])

        assert result == 0
        captured = capsys.readouterr()
        assert "rec_derived" in captured.out
        assert "derived content" in captured.out
