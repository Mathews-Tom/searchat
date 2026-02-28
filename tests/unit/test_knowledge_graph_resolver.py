"""Tests for all 5 resolution strategies in ResolutionEngine."""
from __future__ import annotations

from pathlib import Path

import pytest

from searchat.expertise.models import ExpertiseRecord, ExpertiseType
from searchat.expertise.store import ExpertiseStore
from searchat.knowledge_graph.models import EdgeType, KnowledgeEdge, ResolutionStrategy
from searchat.knowledge_graph.resolver import ResolutionEngine
from searchat.knowledge_graph.store import KnowledgeGraphStore


def _make_record(content: str, domain: str = "test", record_id: str | None = None) -> ExpertiseRecord:
    r = ExpertiseRecord(type=ExpertiseType.PATTERN, domain=domain, content=content)
    if record_id is not None:
        r.id = record_id
    return r


@pytest.fixture
def kg_store(tmp_path: Path) -> KnowledgeGraphStore:
    return KnowledgeGraphStore(data_dir=tmp_path)


@pytest.fixture
def expertise_store(tmp_path: Path) -> ExpertiseStore:
    return ExpertiseStore(data_dir=tmp_path)


@pytest.fixture
def resolver(kg_store: KnowledgeGraphStore, expertise_store: ExpertiseStore) -> ResolutionEngine:
    return ResolutionEngine(kg_store, expertise_store, resolved_by="test_resolver")


@pytest.fixture
def contradiction_edge(
    kg_store: KnowledgeGraphStore,
    expertise_store: ExpertiseStore,
) -> KnowledgeEdge:
    rec_a = _make_record("use tabs", record_id="exp_tabs")
    rec_b = _make_record("never use tabs", record_id="exp_no_tabs")
    expertise_store.insert(rec_a)
    expertise_store.insert(rec_b)
    edge = KnowledgeEdge(
        source_id=rec_a.id,
        target_id=rec_b.id,
        edge_type=EdgeType.CONTRADICTS,
    )
    kg_store.create_edge(edge)
    return edge


class TestSupersede:
    def test_supersede_deactivates_loser(
        self,
        resolver: ResolutionEngine,
        kg_store: KnowledgeGraphStore,
        expertise_store: ExpertiseStore,
        contradiction_edge: KnowledgeEdge,
    ) -> None:
        result = resolver.supersede(contradiction_edge.id, winner_id="exp_tabs")
        assert result.strategy == ResolutionStrategy.SUPERSEDE
        assert "exp_no_tabs" in result.deactivated_records

        loser = expertise_store.get("exp_no_tabs")
        assert loser is not None
        assert loser.is_active is False

        winner = expertise_store.get("exp_tabs")
        assert winner is not None
        assert winner.is_active is True

    def test_supersede_creates_supersedes_edge(
        self,
        resolver: ResolutionEngine,
        kg_store: KnowledgeGraphStore,
        expertise_store: ExpertiseStore,
        contradiction_edge: KnowledgeEdge,
    ) -> None:
        result = resolver.supersede(contradiction_edge.id, winner_id="exp_tabs")
        assert len(result.created_edges) == 1
        sup_edge = kg_store.get_edge(result.created_edges[0])
        assert sup_edge is not None
        assert sup_edge.edge_type == EdgeType.SUPERSEDES
        assert sup_edge.source_id == "exp_tabs"
        assert sup_edge.target_id == "exp_no_tabs"

    def test_supersede_marks_contradiction_resolved(
        self,
        resolver: ResolutionEngine,
        kg_store: KnowledgeGraphStore,
        expertise_store: ExpertiseStore,
        contradiction_edge: KnowledgeEdge,
    ) -> None:
        result = resolver.supersede(contradiction_edge.id, winner_id="exp_tabs")
        updated_edge = kg_store.get_edge(contradiction_edge.id)
        assert updated_edge is not None
        assert updated_edge.resolution_id == result.resolution_id

    def test_supersede_winner_is_target(
        self,
        resolver: ResolutionEngine,
        kg_store: KnowledgeGraphStore,
        expertise_store: ExpertiseStore,
        contradiction_edge: KnowledgeEdge,
    ) -> None:
        # Winner is the target record
        result = resolver.supersede(contradiction_edge.id, winner_id="exp_no_tabs")
        assert "exp_tabs" in result.deactivated_records
        assert "exp_no_tabs" not in result.deactivated_records

    def test_supersede_nonexistent_edge_raises(
        self, resolver: ResolutionEngine
    ) -> None:
        with pytest.raises(ValueError, match="Edge not found"):
            resolver.supersede("nonexistent", winner_id="exp_tabs")


class TestScopeBoth:
    def test_scope_both_updates_content(
        self,
        resolver: ResolutionEngine,
        kg_store: KnowledgeGraphStore,
        expertise_store: ExpertiseStore,
        contradiction_edge: KnowledgeEdge,
    ) -> None:
        result = resolver.scope_both(
            contradiction_edge.id, scope_a="Python files", scope_b="YAML configs"
        )
        assert result.strategy == ResolutionStrategy.SCOPE_BOTH
        rec_a = expertise_store.get("exp_tabs")
        rec_b = expertise_store.get("exp_no_tabs")
        assert rec_a is not None
        assert "Scope: Python files" in rec_a.content
        assert rec_b is not None
        assert "Scope: YAML configs" in rec_b.content

    def test_scope_both_creates_qualifies_edge(
        self,
        resolver: ResolutionEngine,
        kg_store: KnowledgeGraphStore,
        expertise_store: ExpertiseStore,
        contradiction_edge: KnowledgeEdge,
    ) -> None:
        result = resolver.scope_both(contradiction_edge.id, scope_a="A", scope_b="B")
        assert len(result.created_edges) >= 1
        qual_edge = kg_store.get_edge(result.created_edges[0])
        assert qual_edge is not None
        assert qual_edge.edge_type == EdgeType.QUALIFIES

    def test_scope_both_marks_contradiction_resolved(
        self,
        resolver: ResolutionEngine,
        kg_store: KnowledgeGraphStore,
        expertise_store: ExpertiseStore,
        contradiction_edge: KnowledgeEdge,
    ) -> None:
        result = resolver.scope_both(contradiction_edge.id, scope_a="A", scope_b="B")
        updated = kg_store.get_edge(contradiction_edge.id)
        assert updated is not None
        assert updated.resolution_id == result.resolution_id

    def test_scope_both_nonexistent_edge_raises(
        self, resolver: ResolutionEngine
    ) -> None:
        with pytest.raises(ValueError, match="Edge not found"):
            resolver.scope_both("nonexistent", scope_a="A", scope_b="B")


class TestMerge:
    def test_merge_creates_new_record(
        self,
        resolver: ResolutionEngine,
        kg_store: KnowledgeGraphStore,
        expertise_store: ExpertiseStore,
        contradiction_edge: KnowledgeEdge,
    ) -> None:
        result = resolver.merge(contradiction_edge.id, merged_content="use tabs in some contexts")
        assert result.strategy == ResolutionStrategy.MERGE
        assert result.new_record_id is not None
        merged = expertise_store.get(result.new_record_id)
        assert merged is not None
        assert merged.content == "use tabs in some contexts"
        assert merged.is_active is True

    def test_merge_deactivates_originals(
        self,
        resolver: ResolutionEngine,
        kg_store: KnowledgeGraphStore,
        expertise_store: ExpertiseStore,
        contradiction_edge: KnowledgeEdge,
    ) -> None:
        result = resolver.merge(contradiction_edge.id, merged_content="merged content")
        assert set(result.deactivated_records) == {"exp_tabs", "exp_no_tabs"}
        for rec_id in ("exp_tabs", "exp_no_tabs"):
            rec = expertise_store.get(rec_id)
            assert rec is not None
            assert rec.is_active is False

    def test_merge_creates_supersedes_edges(
        self,
        resolver: ResolutionEngine,
        kg_store: KnowledgeGraphStore,
        expertise_store: ExpertiseStore,
        contradiction_edge: KnowledgeEdge,
    ) -> None:
        result = resolver.merge(contradiction_edge.id, merged_content="merged")
        assert len(result.created_edges) == 2
        for edge_id in result.created_edges:
            edge = kg_store.get_edge(edge_id)
            assert edge is not None
            assert edge.edge_type == EdgeType.SUPERSEDES
            assert edge.source_id == result.new_record_id

    def test_merge_nonexistent_edge_raises(
        self, resolver: ResolutionEngine
    ) -> None:
        with pytest.raises(ValueError, match="Edge not found"):
            resolver.merge("nonexistent", merged_content="merged")


class TestDismiss:
    def test_dismiss_creates_resolved_edge(
        self,
        resolver: ResolutionEngine,
        kg_store: KnowledgeGraphStore,
        expertise_store: ExpertiseStore,
        contradiction_edge: KnowledgeEdge,
    ) -> None:
        result = resolver.dismiss(contradiction_edge.id, reason="different contexts")
        assert result.strategy == ResolutionStrategy.DISMISS
        assert len(result.created_edges) == 1
        resolved_edge = kg_store.get_edge(result.created_edges[0])
        assert resolved_edge is not None
        assert resolved_edge.edge_type == EdgeType.RESOLVED
        assert resolved_edge.metadata is not None
        assert resolved_edge.metadata["resolution_strategy"] == "dismiss"
        assert resolved_edge.metadata["reason"] == "different contexts"

    def test_dismiss_marks_contradiction_resolved(
        self,
        resolver: ResolutionEngine,
        kg_store: KnowledgeGraphStore,
        expertise_store: ExpertiseStore,
        contradiction_edge: KnowledgeEdge,
    ) -> None:
        result = resolver.dismiss(contradiction_edge.id, reason="false positive")
        updated = kg_store.get_edge(contradiction_edge.id)
        assert updated is not None
        assert updated.resolution_id == result.resolution_id

    def test_dismiss_keeps_records_active(
        self,
        resolver: ResolutionEngine,
        kg_store: KnowledgeGraphStore,
        expertise_store: ExpertiseStore,
        contradiction_edge: KnowledgeEdge,
    ) -> None:
        resolver.dismiss(contradiction_edge.id, reason="false positive")
        for rec_id in ("exp_tabs", "exp_no_tabs"):
            rec = expertise_store.get(rec_id)
            assert rec is not None
            assert rec.is_active is True

    def test_dismiss_nonexistent_edge_raises(
        self, resolver: ResolutionEngine
    ) -> None:
        with pytest.raises(ValueError, match="Edge not found"):
            resolver.dismiss("nonexistent", reason="reason")


class TestKeepBoth:
    def test_keep_both_creates_resolved_edge(
        self,
        resolver: ResolutionEngine,
        kg_store: KnowledgeGraphStore,
        expertise_store: ExpertiseStore,
        contradiction_edge: KnowledgeEdge,
    ) -> None:
        result = resolver.keep_both(contradiction_edge.id, reason="valid in different regions")
        assert result.strategy == ResolutionStrategy.KEEP_BOTH
        assert len(result.created_edges) == 1
        resolved_edge = kg_store.get_edge(result.created_edges[0])
        assert resolved_edge is not None
        assert resolved_edge.edge_type == EdgeType.RESOLVED
        assert resolved_edge.metadata is not None
        assert resolved_edge.metadata["resolution_strategy"] == "keep_both"
        assert "valid in different regions" in resolved_edge.metadata["reason"]

    def test_keep_both_marks_contradiction_resolved(
        self,
        resolver: ResolutionEngine,
        kg_store: KnowledgeGraphStore,
        expertise_store: ExpertiseStore,
        contradiction_edge: KnowledgeEdge,
    ) -> None:
        result = resolver.keep_both(contradiction_edge.id, reason="acknowledged")
        updated = kg_store.get_edge(contradiction_edge.id)
        assert updated is not None
        assert updated.resolution_id == result.resolution_id

    def test_keep_both_keeps_both_records_active(
        self,
        resolver: ResolutionEngine,
        kg_store: KnowledgeGraphStore,
        expertise_store: ExpertiseStore,
        contradiction_edge: KnowledgeEdge,
    ) -> None:
        resolver.keep_both(contradiction_edge.id, reason="intentional")
        for rec_id in ("exp_tabs", "exp_no_tabs"):
            rec = expertise_store.get(rec_id)
            assert rec is not None
            assert rec.is_active is True

    def test_keep_both_nonexistent_edge_raises(
        self, resolver: ResolutionEngine
    ) -> None:
        with pytest.raises(ValueError, match="Edge not found"):
            resolver.keep_both("nonexistent", reason="reason")


class TestResolutionIDs:
    def test_each_resolution_has_unique_id(
        self,
        resolver: ResolutionEngine,
        kg_store: KnowledgeGraphStore,
        expertise_store: ExpertiseStore,
        tmp_path: Path,
    ) -> None:
        """Resolution IDs must be unique across strategies."""
        resolution_ids: set[str] = set()

        # Create separate contradiction edges for each strategy
        strategies_data = [
            ("exp_a1", "exp_b1", "dismiss"),
            ("exp_a2", "exp_b2", "keep_both"),
        ]
        for source, target, strategy in strategies_data:
            ra = _make_record(f"record {source}", record_id=source)
            rb = _make_record(f"record {target}", record_id=target)
            expertise_store.insert(ra)
            expertise_store.insert(rb)
            edge = KnowledgeEdge(source_id=source, target_id=target, edge_type=EdgeType.CONTRADICTS)
            kg_store.create_edge(edge)
            if strategy == "dismiss":
                result = resolver.dismiss(edge.id, reason="test")
            else:
                result = resolver.keep_both(edge.id, reason="test")
            assert result.resolution_id not in resolution_ids
            resolution_ids.add(result.resolution_id)
