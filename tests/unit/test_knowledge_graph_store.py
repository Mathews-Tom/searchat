"""Tests for KnowledgeGraphStore edge CRUD and query operations."""
from __future__ import annotations

from pathlib import Path

import pytest

from searchat.knowledge_graph.models import EdgeType, KnowledgeEdge
from searchat.knowledge_graph.store import KnowledgeGraphStore


@pytest.fixture
def kg_store(tmp_path: Path) -> KnowledgeGraphStore:
    return KnowledgeGraphStore(data_dir=tmp_path)


@pytest.fixture
def sample_edge() -> KnowledgeEdge:
    return KnowledgeEdge(
        source_id="exp_source001",
        target_id="exp_target001",
        edge_type=EdgeType.CONTRADICTS,
        created_by="test_agent",
    )


class TestEdgeCRUD:
    def test_create_and_get_edge(self, kg_store: KnowledgeGraphStore, sample_edge: KnowledgeEdge) -> None:
        edge_id = kg_store.create_edge(sample_edge)
        assert edge_id == sample_edge.id
        fetched = kg_store.get_edge(edge_id)
        assert fetched is not None
        assert fetched.id == edge_id
        assert fetched.source_id == sample_edge.source_id
        assert fetched.target_id == sample_edge.target_id
        assert fetched.edge_type == EdgeType.CONTRADICTS

    def test_get_edge_not_found(self, kg_store: KnowledgeGraphStore) -> None:
        assert kg_store.get_edge("nonexistent") is None

    def test_delete_edge(self, kg_store: KnowledgeGraphStore, sample_edge: KnowledgeEdge) -> None:
        kg_store.create_edge(sample_edge)
        assert kg_store.delete_edge(sample_edge.id) is True
        assert kg_store.get_edge(sample_edge.id) is None

    def test_delete_edge_not_found(self, kg_store: KnowledgeGraphStore) -> None:
        assert kg_store.delete_edge("nonexistent") is False

    def test_update_edge_resolution_id(self, kg_store: KnowledgeGraphStore, sample_edge: KnowledgeEdge) -> None:
        kg_store.create_edge(sample_edge)
        assert kg_store.update_edge(sample_edge.id, resolution_id="res_abc") is True
        fetched = kg_store.get_edge(sample_edge.id)
        assert fetched is not None
        assert fetched.resolution_id == "res_abc"

    def test_update_edge_invalid_field_raises(self, kg_store: KnowledgeGraphStore, sample_edge: KnowledgeEdge) -> None:
        kg_store.create_edge(sample_edge)
        with pytest.raises(ValueError, match="Cannot update fields"):
            kg_store.update_edge(sample_edge.id, nonexistent_field="bad")

    def test_update_edge_not_found_returns_false(self, kg_store: KnowledgeGraphStore) -> None:
        assert kg_store.update_edge("ghost_id", resolution_id="res_x") is False

    def test_edge_with_metadata(self, kg_store: KnowledgeGraphStore) -> None:
        edge = KnowledgeEdge(
            source_id="a",
            target_id="b",
            edge_type=EdgeType.DEPENDS_ON,
            metadata={"reason": "test", "priority": 1},
        )
        kg_store.create_edge(edge)
        fetched = kg_store.get_edge(edge.id)
        assert fetched is not None
        assert fetched.metadata == {"reason": "test", "priority": 1}

    def test_edge_without_metadata(self, kg_store: KnowledgeGraphStore) -> None:
        edge = KnowledgeEdge(
            source_id="x",
            target_id="y",
            edge_type=EdgeType.DERIVED_FROM,
        )
        kg_store.create_edge(edge)
        fetched = kg_store.get_edge(edge.id)
        assert fetched is not None
        assert fetched.metadata is None


class TestEdgeQueryByType:
    def test_get_contradictions_unresolved_only(self, kg_store: KnowledgeGraphStore) -> None:
        e1 = KnowledgeEdge(source_id="a", target_id="b", edge_type=EdgeType.CONTRADICTS)
        e2 = KnowledgeEdge(source_id="c", target_id="d", edge_type=EdgeType.CONTRADICTS)
        e3 = KnowledgeEdge(source_id="e", target_id="f", edge_type=EdgeType.SUPERSEDES)
        kg_store.create_edge(e1)
        kg_store.create_edge(e2)
        kg_store.create_edge(e3)

        contradictions = kg_store.get_contradictions(unresolved_only=True)
        assert len(contradictions) == 2
        ids = {c.id for c in contradictions}
        assert e1.id in ids
        assert e2.id in ids

    def test_get_contradictions_excludes_resolved(self, kg_store: KnowledgeGraphStore) -> None:
        e1 = KnowledgeEdge(source_id="a", target_id="b", edge_type=EdgeType.CONTRADICTS)
        e2 = KnowledgeEdge(source_id="c", target_id="d", edge_type=EdgeType.CONTRADICTS)
        kg_store.create_edge(e1)
        kg_store.create_edge(e2)
        kg_store.update_edge(e1.id, resolution_id="res_001")

        unresolved = kg_store.get_contradictions(unresolved_only=True)
        assert len(unresolved) == 1
        assert unresolved[0].id == e2.id

    def test_get_contradictions_all(self, kg_store: KnowledgeGraphStore) -> None:
        e1 = KnowledgeEdge(source_id="a", target_id="b", edge_type=EdgeType.CONTRADICTS)
        kg_store.create_edge(e1)
        kg_store.update_edge(e1.id, resolution_id="res_001")
        all_contradictions = kg_store.get_contradictions(unresolved_only=False)
        assert len(all_contradictions) == 1

    def test_get_related_returns_all_edge_types(self, kg_store: KnowledgeGraphStore) -> None:
        center = "exp_center"
        e1 = KnowledgeEdge(source_id=center, target_id="exp_a", edge_type=EdgeType.SUPERSEDES)
        e2 = KnowledgeEdge(source_id="exp_b", target_id=center, edge_type=EdgeType.DEPENDS_ON)
        e3 = KnowledgeEdge(source_id="exp_c", target_id="exp_d", edge_type=EdgeType.QUALIFIES)
        kg_store.create_edge(e1)
        kg_store.create_edge(e2)
        kg_store.create_edge(e3)

        related = kg_store.get_related(center)
        related_ids = {e.id for e in related}
        assert e1.id in related_ids
        assert e2.id in related_ids
        assert e3.id not in related_ids

    def test_get_related_filtered_by_type(self, kg_store: KnowledgeGraphStore) -> None:
        center = "exp_center2"
        e1 = KnowledgeEdge(source_id=center, target_id="x", edge_type=EdgeType.SUPERSEDES)
        e2 = KnowledgeEdge(source_id=center, target_id="y", edge_type=EdgeType.CONTRADICTS)
        kg_store.create_edge(e1)
        kg_store.create_edge(e2)

        related = kg_store.get_related(center, edge_types=[EdgeType.SUPERSEDES])
        assert len(related) == 1
        assert related[0].id == e1.id


class TestEdgeQueryByRecord:
    def test_get_edges_for_record_as_source(self, kg_store: KnowledgeGraphStore) -> None:
        record_id = "exp_rec001"
        e1 = KnowledgeEdge(source_id=record_id, target_id="exp_other", edge_type=EdgeType.DERIVED_FROM)
        e2 = KnowledgeEdge(source_id="exp_third", target_id=record_id, edge_type=EdgeType.CONTRADICTS)
        kg_store.create_edge(e1)
        kg_store.create_edge(e2)

        edges = kg_store.get_edges_for_record(record_id, as_source=True, as_target=False)
        assert len(edges) == 1
        assert edges[0].id == e1.id

    def test_get_edges_for_record_as_target(self, kg_store: KnowledgeGraphStore) -> None:
        record_id = "exp_rec002"
        e1 = KnowledgeEdge(source_id=record_id, target_id="exp_other", edge_type=EdgeType.DERIVED_FROM)
        e2 = KnowledgeEdge(source_id="exp_third", target_id=record_id, edge_type=EdgeType.CONTRADICTS)
        kg_store.create_edge(e1)
        kg_store.create_edge(e2)

        edges = kg_store.get_edges_for_record(record_id, as_source=False, as_target=True)
        assert len(edges) == 1
        assert edges[0].id == e2.id

    def test_get_edges_for_record_both_directions(self, kg_store: KnowledgeGraphStore) -> None:
        record_id = "exp_rec003"
        e1 = KnowledgeEdge(source_id=record_id, target_id="x", edge_type=EdgeType.SUPERSEDES)
        e2 = KnowledgeEdge(source_id="y", target_id=record_id, edge_type=EdgeType.DEPENDS_ON)
        kg_store.create_edge(e1)
        kg_store.create_edge(e2)

        edges = kg_store.get_edges_for_record(record_id, as_source=True, as_target=True)
        ids = {e.id for e in edges}
        assert e1.id in ids
        assert e2.id in ids

    def test_get_edges_for_record_filtered_by_type(self, kg_store: KnowledgeGraphStore) -> None:
        record_id = "exp_rec004"
        e1 = KnowledgeEdge(source_id=record_id, target_id="x", edge_type=EdgeType.SUPERSEDES)
        e2 = KnowledgeEdge(source_id=record_id, target_id="y", edge_type=EdgeType.DERIVED_FROM)
        kg_store.create_edge(e1)
        kg_store.create_edge(e2)

        edges = kg_store.get_edges_for_record(
            record_id, edge_type=EdgeType.SUPERSEDES, as_source=True, as_target=False
        )
        assert len(edges) == 1
        assert edges[0].id == e1.id

    def test_get_edges_for_record_no_direction_returns_empty(self, kg_store: KnowledgeGraphStore) -> None:
        record_id = "exp_rec005"
        e1 = KnowledgeEdge(source_id=record_id, target_id="x", edge_type=EdgeType.SUPERSEDES)
        kg_store.create_edge(e1)
        edges = kg_store.get_edges_for_record(record_id, as_source=False, as_target=False)
        assert edges == []


class TestBulkOperations:
    def test_bulk_create_edges(self, kg_store: KnowledgeGraphStore) -> None:
        edges = [
            KnowledgeEdge(source_id=f"s{i}", target_id=f"t{i}", edge_type=EdgeType.QUALIFIES)
            for i in range(5)
        ]
        ids = kg_store.bulk_create_edges(edges)
        assert len(ids) == 5
        for e in edges:
            assert kg_store.get_edge(e.id) is not None

    def test_bulk_create_edges_empty(self, kg_store: KnowledgeGraphStore) -> None:
        assert kg_store.bulk_create_edges([]) == []

    def test_bulk_delete_edges(self, kg_store: KnowledgeGraphStore) -> None:
        edges = [
            KnowledgeEdge(source_id=f"src{i}", target_id=f"tgt{i}", edge_type=EdgeType.RESOLVED)
            for i in range(3)
        ]
        kg_store.bulk_create_edges(edges)
        count = kg_store.bulk_delete_edges([e.id for e in edges[:2]])
        assert count == 2
        assert kg_store.get_edge(edges[0].id) is None
        assert kg_store.get_edge(edges[1].id) is None
        assert kg_store.get_edge(edges[2].id) is not None

    def test_bulk_delete_edges_empty(self, kg_store: KnowledgeGraphStore) -> None:
        assert kg_store.bulk_delete_edges([]) == 0
