"""Tests for ProvenanceTracker lineage tracking."""
from __future__ import annotations

from pathlib import Path

import pytest

from searchat.expertise.models import ExpertiseRecord, ExpertiseType
from searchat.knowledge_graph.models import EdgeType
from searchat.knowledge_graph.provenance import ProvenanceTracker
from searchat.knowledge_graph.store import KnowledgeGraphStore


def _make_record(content: str, domain: str = "test", record_id: str | None = None) -> ExpertiseRecord:
    r = ExpertiseRecord(type=ExpertiseType.INSIGHT, domain=domain, content=content)
    if record_id is not None:
        r.id = record_id
    return r


@pytest.fixture
def kg_store(tmp_path: Path) -> KnowledgeGraphStore:
    return KnowledgeGraphStore(data_dir=tmp_path)


@pytest.fixture
def tracker(kg_store: KnowledgeGraphStore) -> ProvenanceTracker:
    return ProvenanceTracker(kg_store, created_by="test_tracker")


class TestRecordExtraction:
    def test_record_extraction_creates_derived_from_edge(
        self,
        tracker: ProvenanceTracker,
        kg_store: KnowledgeGraphStore,
    ) -> None:
        record = _make_record("use dependency injection", record_id="exp_di001")
        edge_id = tracker.record_extraction(record, conversation_id="conv_001")

        edge = kg_store.get_edge(edge_id)
        assert edge is not None
        assert edge.edge_type == EdgeType.DERIVED_FROM
        assert edge.source_id == record.id
        assert edge.target_id == "conv_001"

    def test_record_extraction_stores_metadata(
        self,
        tracker: ProvenanceTracker,
        kg_store: KnowledgeGraphStore,
    ) -> None:
        record = _make_record("prefer composition over inheritance", record_id="exp_comp001")
        record.source_agent = "claude-opus"
        edge_id = tracker.record_extraction(record, conversation_id="conv_002", agent="claude-opus")

        edge = kg_store.get_edge(edge_id)
        assert edge is not None
        assert edge.metadata is not None
        assert edge.metadata["conversation_id"] == "conv_002"
        assert edge.metadata["record_domain"] == "test"
        assert edge.metadata["record_type"] == "insight"

    def test_record_extraction_returns_edge_id(
        self,
        tracker: ProvenanceTracker,
    ) -> None:
        record = _make_record("always validate inputs", record_id="exp_val001")
        edge_id = tracker.record_extraction(record, conversation_id="conv_003")
        assert isinstance(edge_id, str)
        assert len(edge_id) > 0

    def test_multiple_extractions_same_conversation(
        self,
        tracker: ProvenanceTracker,
        kg_store: KnowledgeGraphStore,
    ) -> None:
        conv_id = "conv_multi_001"
        records = [
            _make_record(f"insight {i}", record_id=f"exp_multi_{i:03d}")
            for i in range(3)
        ]
        for rec in records:
            tracker.record_extraction(rec, conversation_id=conv_id)

        record_ids = tracker.get_records_from_conversation(conv_id)
        assert set(record_ids) == {r.id for r in records}


class TestForwardLineage:
    def test_get_conversations_for_record(
        self, tracker: ProvenanceTracker
    ) -> None:
        record = _make_record("use immutable data", record_id="exp_imm001")
        tracker.record_extraction(record, conversation_id="conv_a")
        tracker.record_extraction(record, conversation_id="conv_b")

        conversations = tracker.get_conversations_for_record(record.id)
        assert set(conversations) == {"conv_a", "conv_b"}

    def test_get_conversations_for_record_none(
        self, tracker: ProvenanceTracker
    ) -> None:
        conversations = tracker.get_conversations_for_record("exp_nonexistent")
        assert conversations == []

    def test_get_conversations_isolation(
        self, tracker: ProvenanceTracker
    ) -> None:
        """Each record only sees its own conversation lineage."""
        rec_a = _make_record("insight a", record_id="exp_iso_a")
        rec_b = _make_record("insight b", record_id="exp_iso_b")
        tracker.record_extraction(rec_a, conversation_id="conv_only_a")
        tracker.record_extraction(rec_b, conversation_id="conv_only_b")

        assert tracker.get_conversations_for_record(rec_a.id) == ["conv_only_a"]
        assert tracker.get_conversations_for_record(rec_b.id) == ["conv_only_b"]


class TestReverseLineage:
    def test_get_records_from_conversation(
        self, tracker: ProvenanceTracker
    ) -> None:
        conv_id = "conv_rev_001"
        rec_a = _make_record("insight alpha", record_id="exp_rev_a")
        rec_b = _make_record("insight beta", record_id="exp_rev_b")
        tracker.record_extraction(rec_a, conversation_id=conv_id)
        tracker.record_extraction(rec_b, conversation_id=conv_id)

        record_ids = tracker.get_records_from_conversation(conv_id)
        assert set(record_ids) == {rec_a.id, rec_b.id}

    def test_get_records_from_conversation_none(
        self, tracker: ProvenanceTracker
    ) -> None:
        record_ids = tracker.get_records_from_conversation("conv_nonexistent")
        assert record_ids == []


class TestFullLineage:
    def test_get_full_lineage_conversations(
        self, tracker: ProvenanceTracker
    ) -> None:
        record = _make_record("follow SOLID principles", record_id="exp_solid_001")
        tracker.record_extraction(record, conversation_id="conv_solid_1")
        tracker.record_extraction(record, conversation_id="conv_solid_2")

        lineage = tracker.get_full_lineage(record.id)
        assert set(lineage["conversations"]) == {"conv_solid_1", "conv_solid_2"}

    def test_get_full_lineage_derived_records(
        self, tracker: ProvenanceTracker
    ) -> None:
        """Sibling records from the same conversation appear in derived_records."""
        conv_id = "conv_siblings"
        rec_a = _make_record("insight a", record_id="exp_sib_a")
        rec_b = _make_record("insight b", record_id="exp_sib_b")
        rec_c = _make_record("insight c", record_id="exp_sib_c")
        tracker.record_extraction(rec_a, conversation_id=conv_id)
        tracker.record_extraction(rec_b, conversation_id=conv_id)
        tracker.record_extraction(rec_c, conversation_id=conv_id)

        lineage = tracker.get_full_lineage(rec_a.id)
        assert rec_a.id not in lineage["derived_records"]
        assert rec_b.id in lineage["derived_records"]
        assert rec_c.id in lineage["derived_records"]

    def test_get_full_lineage_empty_for_untracked(
        self, tracker: ProvenanceTracker
    ) -> None:
        lineage = tracker.get_full_lineage("exp_untracked_001")
        assert lineage["conversations"] == []
        assert lineage["derived_records"] == []
