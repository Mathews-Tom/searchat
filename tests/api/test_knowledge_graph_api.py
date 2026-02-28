"""API tests for the Knowledge Graph endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from searchat.api.app import app
from searchat.knowledge_graph.models import EdgeType, KnowledgeEdge, ResolutionStrategy


@pytest.fixture
def client():
    return TestClient(app)


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


def _mock_kg_config():
    return SimpleNamespace(
        knowledge_graph=SimpleNamespace(
            enabled=True,
            similarity_threshold=0.75,
            contradiction_threshold=0.70,
            nli_model="cross-encoder/nli-deberta-v3-xsmall",
        ),
        expertise=SimpleNamespace(enabled=True),
    )


@pytest.fixture
def mock_kg_store():
    return MagicMock()


@pytest.fixture
def mock_expertise_store():
    return MagicMock()


@pytest.fixture
def patched_stores(mock_kg_store, mock_expertise_store):
    with (
        patch(
            "searchat.api.routers.knowledge_graph.get_knowledge_graph_store",
            return_value=mock_kg_store,
        ),
        patch(
            "searchat.api.routers.knowledge_graph.get_expertise_store",
            return_value=mock_expertise_store,
        ),
        patch(
            "searchat.api.routers.knowledge_graph.get_config",
            return_value=_mock_kg_config(),
        ),
    ):
        yield mock_kg_store, mock_expertise_store


# ---------------------------------------------------------------------------
# GET /api/knowledge-graph/contradictions
# ---------------------------------------------------------------------------


class TestListContradictions:
    def test_empty_returns_empty_list(self, client, patched_stores):
        kg_store, _ = patched_stores
        kg_store.get_contradictions.return_value = []

        resp = client.get("/api/knowledge-graph/contradictions")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["results"] == []
        assert data["unresolved_only"] is True

    def test_returns_contradiction_list(self, client, patched_stores):
        kg_store, _ = patched_stores
        edge = _make_edge()
        kg_store.get_contradictions.return_value = [edge]

        resp = client.get("/api/knowledge-graph/contradictions")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        item = data["results"][0]
        assert item["edge_id"] == edge.id
        assert item["record_id_a"] == "rec_aaa"
        assert item["record_id_b"] == "rec_bbb"
        assert item["resolution_id"] is None

    def test_unresolved_only_false(self, client, patched_stores):
        kg_store, _ = patched_stores
        edge = _make_edge(resolution_id="res_xyz")
        kg_store.get_contradictions.return_value = [edge]

        resp = client.get("/api/knowledge-graph/contradictions?unresolved_only=false")

        assert resp.status_code == 200
        data = resp.json()
        assert data["unresolved_only"] is False
        kg_store.get_contradictions.assert_called_once_with(unresolved_only=False)

    def test_filters_by_domain(self, client, patched_stores):
        kg_store, expertise_store = patched_stores
        edge_a = _make_edge(source_id="rec_auth_1", target_id="rec_auth_2")
        edge_b = _make_edge(source_id="rec_db_1", target_id="rec_db_2")
        kg_store.get_contradictions.return_value = [edge_a, edge_b]

        rec_auth = MagicMock()
        rec_auth.domain = "auth"
        rec_db = MagicMock()
        rec_db.domain = "db"

        def _get(rid):
            if rid in ("rec_auth_1", "rec_auth_2"):
                return rec_auth
            return rec_db

        expertise_store.get.side_effect = _get

        resp = client.get("/api/knowledge-graph/contradictions?domain=auth")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["results"][0]["record_id_a"] == "rec_auth_1"


# ---------------------------------------------------------------------------
# POST /api/knowledge-graph/resolve
# ---------------------------------------------------------------------------


class TestResolveContradiction:
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

    def test_dismiss_strategy(self, client, patched_stores):
        kg_store, expertise_store = patched_stores
        edge = _make_edge()
        kg_store.get_edge.return_value = edge
        result = self._make_resolution_result(ResolutionStrategy.DISMISS)

        with patch(
            "searchat.knowledge_graph.resolver.ResolutionEngine"
        ) as MockEngine:
            instance = MockEngine.return_value
            instance.dismiss.return_value = result

            resp = client.post(
                "/api/knowledge-graph/resolve",
                json={
                    "edge_id": "edge_abc",
                    "strategy": "dismiss",
                    "params": {"reason": "Not a real contradiction"},
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["strategy"] == "dismiss"
        assert data["resolution_id"] == result.resolution_id
        instance.dismiss.assert_called_once_with("edge_abc", "Not a real contradiction")

    def test_supersede_strategy(self, client, patched_stores):
        kg_store, expertise_store = patched_stores
        edge = _make_edge()
        kg_store.get_edge.return_value = edge
        result = self._make_resolution_result(ResolutionStrategy.SUPERSEDE)

        with patch(
            "searchat.knowledge_graph.resolver.ResolutionEngine"
        ) as MockEngine:
            instance = MockEngine.return_value
            instance.supersede.return_value = result

            resp = client.post(
                "/api/knowledge-graph/resolve",
                json={
                    "edge_id": "edge_abc",
                    "strategy": "supersede",
                    "params": {"winner_id": "rec_aaa"},
                },
            )

        assert resp.status_code == 200
        instance.supersede.assert_called_once_with("edge_abc", "rec_aaa")

    def test_missing_edge_returns_404(self, client, patched_stores):
        kg_store, _ = patched_stores
        kg_store.get_edge.return_value = None

        resp = client.post(
            "/api/knowledge-graph/resolve",
            json={"edge_id": "nonexistent", "strategy": "dismiss", "params": {"reason": "x"}},
        )

        assert resp.status_code == 404

    def test_non_contradiction_edge_returns_422(self, client, patched_stores):
        kg_store, _ = patched_stores
        edge = _make_edge(edge_type=EdgeType.SUPERSEDES)
        kg_store.get_edge.return_value = edge

        resp = client.post(
            "/api/knowledge-graph/resolve",
            json={"edge_id": edge.id, "strategy": "dismiss", "params": {"reason": "x"}},
        )

        assert resp.status_code == 422

    def test_invalid_strategy_returns_422(self, client, patched_stores):
        kg_store, _ = patched_stores
        edge = _make_edge()
        kg_store.get_edge.return_value = edge

        resp = client.post(
            "/api/knowledge-graph/resolve",
            json={"edge_id": edge.id, "strategy": "invalid_strategy", "params": {}},
        )

        assert resp.status_code == 422

    def test_missing_required_param_returns_422(self, client, patched_stores):
        kg_store, _ = patched_stores
        edge = _make_edge()
        kg_store.get_edge.return_value = edge

        resp = client.post(
            "/api/knowledge-graph/resolve",
            json={"edge_id": edge.id, "strategy": "dismiss", "params": {}},
        )

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/knowledge-graph/lineage/{record_id}
# ---------------------------------------------------------------------------


class TestGetLineage:
    def test_returns_lineage(self, client, patched_stores):
        kg_store, expertise_store = patched_stores
        rec = MagicMock()
        expertise_store.get.return_value = rec

        with patch(
            "searchat.knowledge_graph.provenance.ProvenanceTracker"
        ) as MockTracker:
            instance = MockTracker.return_value
            instance.get_full_lineage.return_value = {
                "conversations": ["conv_1", "conv_2"],
                "derived_records": ["rec_derived"],
            }

            resp = client.get("/api/knowledge-graph/lineage/rec_123")

        assert resp.status_code == 200
        data = resp.json()
        assert data["record_id"] == "rec_123"
        assert data["conversations"] == ["conv_1", "conv_2"]
        assert data["derived_records"] == ["rec_derived"]

    def test_missing_record_returns_404(self, client, patched_stores):
        _, expertise_store = patched_stores
        expertise_store.get.return_value = None

        resp = client.get("/api/knowledge-graph/lineage/nonexistent")

        assert resp.status_code == 404

    def test_empty_lineage(self, client, patched_stores):
        kg_store, expertise_store = patched_stores
        expertise_store.get.return_value = MagicMock()

        with patch(
            "searchat.knowledge_graph.provenance.ProvenanceTracker"
        ) as MockTracker:
            instance = MockTracker.return_value
            instance.get_full_lineage.return_value = {
                "conversations": [],
                "derived_records": [],
            }

            resp = client.get("/api/knowledge-graph/lineage/rec_123")

        assert resp.status_code == 200
        data = resp.json()
        assert data["conversations"] == []
        assert data["derived_records"] == []


# ---------------------------------------------------------------------------
# GET /api/knowledge-graph/related/{record_id}
# ---------------------------------------------------------------------------


class TestGetRelated:
    def test_returns_related_edges(self, client, patched_stores):
        kg_store, expertise_store = patched_stores
        expertise_store.get.return_value = MagicMock()
        edge = _make_edge(edge_type=EdgeType.QUALIFIES)
        kg_store.get_related.return_value = [edge]

        resp = client.get("/api/knowledge-graph/related/rec_123")

        assert resp.status_code == 200
        data = resp.json()
        assert data["record_id"] == "rec_123"
        assert data["total"] == 1
        assert data["edges"][0]["edge_type"] == "qualifies"

    def test_missing_record_returns_404(self, client, patched_stores):
        _, expertise_store = patched_stores
        expertise_store.get.return_value = None

        resp = client.get("/api/knowledge-graph/related/nonexistent")

        assert resp.status_code == 404

    def test_filters_by_edge_types(self, client, patched_stores):
        kg_store, expertise_store = patched_stores
        expertise_store.get.return_value = MagicMock()
        kg_store.get_related.return_value = []

        resp = client.get("/api/knowledge-graph/related/rec_123?edge_types=supersedes,qualifies")

        assert resp.status_code == 200
        kg_store.get_related.assert_called_once_with(
            "rec_123",
            edge_types=[EdgeType.SUPERSEDES, EdgeType.QUALIFIES],
            limit=20,
        )

    def test_invalid_edge_type_returns_422(self, client, patched_stores):
        _, expertise_store = patched_stores
        expertise_store.get.return_value = MagicMock()

        resp = client.get("/api/knowledge-graph/related/rec_123?edge_types=invalid_type")

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/knowledge-graph/stats
# ---------------------------------------------------------------------------


class TestGraphStats:
    def test_returns_stats_shape(self, client, patched_stores):
        kg_store, expertise_store = patched_stores

        from searchat.expertise.models import ExpertiseQuery

        mock_rec = MagicMock()
        mock_rec.id = "rec_1"
        expertise_store.query.return_value = [mock_rec]
        kg_store.get_contradictions.side_effect = lambda unresolved_only: []
        kg_store.get_edges_for_record.return_value = []

        resp = client.get("/api/knowledge-graph/stats")

        assert resp.status_code == 200
        data = resp.json()
        assert "node_count" in data
        assert "edge_count" in data
        assert "contradiction_count" in data
        assert "unresolved_contradiction_count" in data
        assert "contradiction_rate" in data
        assert "health_score" in data
        assert "edge_type_counts" in data

    def test_health_score_is_1_when_no_contradictions(self, client, patched_stores):
        kg_store, expertise_store = patched_stores
        mock_rec = MagicMock()
        mock_rec.id = "rec_1"
        expertise_store.query.return_value = [mock_rec]
        kg_store.get_contradictions.return_value = []
        kg_store.get_edges_for_record.return_value = []

        resp = client.get("/api/knowledge-graph/stats")

        assert resp.status_code == 200
        assert resp.json()["health_score"] == 1.0

    def test_contradiction_rate_computed(self, client, patched_stores):
        kg_store, expertise_store = patched_stores
        recs = [MagicMock(id=f"rec_{i}") for i in range(10)]
        expertise_store.query.return_value = recs
        contra_edge = _make_edge()
        kg_store.get_contradictions.return_value = [contra_edge]
        kg_store.get_edges_for_record.return_value = []

        resp = client.get("/api/knowledge-graph/stats")

        assert resp.status_code == 200
        data = resp.json()
        assert data["contradiction_count"] == 1
        assert abs(data["contradiction_rate"] - 0.1) < 0.001


# ---------------------------------------------------------------------------
# GET /api/knowledge-graph/domain-map
# ---------------------------------------------------------------------------


class TestDomainMap:
    def test_returns_domain_map_shape(self, client, patched_stores):
        kg_store, expertise_store = patched_stores
        expertise_store.query.return_value = []
        kg_store.get_edges_for_record.return_value = []

        resp = client.get("/api/knowledge-graph/domain-map")

        assert resp.status_code == 200
        data = resp.json()
        assert "entries" in data
        assert "domains" in data
        assert "total_cross_domain_edges" in data

    def test_cross_domain_edge_counted(self, client, patched_stores):
        kg_store, expertise_store = patched_stores

        rec_a = MagicMock(id="rec_a", domain="auth")
        rec_b = MagicMock(id="rec_b", domain="db")
        expertise_store.query.return_value = [rec_a, rec_b]

        edge = _make_edge(source_id="rec_a", target_id="rec_b", edge_type=EdgeType.DEPENDS_ON)

        def _get_edges(record_id, as_source=True, as_target=True):
            if record_id == "rec_a" and as_source:
                return [edge]
            return []

        kg_store.get_edges_for_record.side_effect = _get_edges

        resp = client.get("/api/knowledge-graph/domain-map")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cross_domain_edges"] == 1
        assert len(data["entries"]) == 1
        entry = data["entries"][0]
        assert entry["source_domain"] == "auth"
        assert entry["target_domain"] == "db"
        assert entry["edge_type"] == "depends_on"


# ---------------------------------------------------------------------------
# POST /api/knowledge-graph/edges
# ---------------------------------------------------------------------------


class TestCreateEdge:
    def test_creates_edge_successfully(self, client, patched_stores):
        kg_store, expertise_store = patched_stores
        expertise_store.get.return_value = MagicMock()

        resp = client.post(
            "/api/knowledge-graph/edges",
            json={
                "source_id": "rec_aaa",
                "target_id": "rec_bbb",
                "edge_type": "qualifies",
            },
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["source_id"] == "rec_aaa"
        assert data["target_id"] == "rec_bbb"
        assert data["edge_type"] == "qualifies"
        kg_store.create_edge.assert_called_once()

    def test_missing_source_record_returns_404(self, client, patched_stores):
        _, expertise_store = patched_stores

        def _get(rid):
            if rid == "rec_aaa":
                return None
            return MagicMock()

        expertise_store.get.side_effect = _get

        resp = client.post(
            "/api/knowledge-graph/edges",
            json={
                "source_id": "rec_aaa",
                "target_id": "rec_bbb",
                "edge_type": "qualifies",
            },
        )

        assert resp.status_code == 404

    def test_missing_target_record_returns_404(self, client, patched_stores):
        _, expertise_store = patched_stores

        def _get(rid):
            if rid == "rec_bbb":
                return None
            return MagicMock()

        expertise_store.get.side_effect = _get

        resp = client.post(
            "/api/knowledge-graph/edges",
            json={
                "source_id": "rec_aaa",
                "target_id": "rec_bbb",
                "edge_type": "qualifies",
            },
        )

        assert resp.status_code == 404

    def test_invalid_edge_type_returns_422(self, client, patched_stores):
        _, expertise_store = patched_stores
        expertise_store.get.return_value = MagicMock()

        resp = client.post(
            "/api/knowledge-graph/edges",
            json={
                "source_id": "rec_aaa",
                "target_id": "rec_bbb",
                "edge_type": "bad_type",
            },
        )

        assert resp.status_code == 422

    def test_with_metadata(self, client, patched_stores):
        kg_store, expertise_store = patched_stores
        expertise_store.get.return_value = MagicMock()

        resp = client.post(
            "/api/knowledge-graph/edges",
            json={
                "source_id": "rec_aaa",
                "target_id": "rec_bbb",
                "edge_type": "depends_on",
                "metadata": {"note": "critical dependency"},
                "created_by": "test_agent",
            },
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["metadata"] == {"note": "critical dependency"}
        assert data["created_by"] == "test_agent"


# ---------------------------------------------------------------------------
# DELETE /api/knowledge-graph/edges/{edge_id}
# ---------------------------------------------------------------------------


class TestDeleteEdge:
    def test_deletes_existing_edge(self, client, patched_stores):
        kg_store, _ = patched_stores
        edge = _make_edge()
        kg_store.get_edge.return_value = edge

        resp = client.delete(f"/api/knowledge-graph/edges/{edge.id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "deleted"
        assert data["id"] == edge.id
        kg_store.delete_edge.assert_called_once_with(edge.id)

    def test_missing_edge_returns_404(self, client, patched_stores):
        kg_store, _ = patched_stores
        kg_store.get_edge.return_value = None

        resp = client.delete("/api/knowledge-graph/edges/nonexistent")

        assert resp.status_code == 404
        kg_store.delete_edge.assert_not_called()
