"""Tests for KG-aware filtering and annotation in ExpertisePrioritizer."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from searchat.expertise.models import ExpertiseRecord, ExpertiseSeverity, ExpertiseType, PrimeResult
from searchat.expertise.primer import ExpertisePrioritizer, PrimeFormatter
from searchat.knowledge_graph.models import EdgeType, KnowledgeEdge


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_record(
    record_id: str = "rec-1",
    type_: ExpertiseType = ExpertiseType.CONVENTION,
    content: str = "Always use type annotations",
    domain: str = "python",
    **kwargs,
) -> ExpertiseRecord:
    defaults = {
        "type": type_,
        "domain": domain,
        "content": content,
        "created_at": _utcnow(),
        "last_validated": _utcnow(),
    }
    defaults.update(kwargs)
    r = ExpertiseRecord(**defaults)
    object.__setattr__(r, "id", record_id)
    return r


def _make_edge(
    source_id: str,
    target_id: str,
    edge_type: EdgeType,
    resolution_id: str | None = None,
) -> KnowledgeEdge:
    return KnowledgeEdge(
        source_id=source_id,
        target_id=target_id,
        edge_type=edge_type,
        resolution_id=resolution_id,
    )


class FakeKGStore:
    """Fake KG store returning controlled edges."""

    def __init__(self, edges: list[KnowledgeEdge] | None = None):
        self._edges = edges or []

    def get_edges_for_record(
        self, record_id: str, as_source: bool = True, as_target: bool = True
    ) -> list[KnowledgeEdge]:
        result = []
        for e in self._edges:
            if as_source and e.source_id == record_id:
                result.append(e)
            if as_target and e.target_id == record_id:
                result.append(e)
        return result


class TestPrioritizerKGFiltering:
    def test_superseded_records_excluded(self):
        """Records with incoming SUPERSEDES edges should be filtered out."""
        old = _make_record("old-rec", content="Use Python 2")
        new = _make_record("new-rec", content="Use Python 3")

        edges = [_make_edge("new-rec", "old-rec", EdgeType.SUPERSEDES)]
        kg = FakeKGStore(edges)

        prioritizer = ExpertisePrioritizer()
        result = prioritizer.prioritize([old, new], kg_store=kg)

        ids = [r.id for r in result.expertise]
        assert "old-rec" not in ids
        assert "new-rec" in ids

    def test_qualifying_notes_annotated(self):
        """Records with incoming QUALIFIES edges should have qualifying metadata."""
        base = _make_record("base-rec", content="Use SQLAlchemy")
        qualifier = _make_record("qual-rec", content="Except for read-only queries")

        edges = [_make_edge("qual-rec", "base-rec", EdgeType.QUALIFIES)]
        kg = FakeKGStore(edges)

        prioritizer = ExpertisePrioritizer()
        prioritizer.prioritize([base, qualifier], kg_store=kg)

        assert "base-rec" in prioritizer._qualifying_notes
        assert "qual-rec" in prioritizer._qualifying_notes["base-rec"]

    def test_contradiction_ids_tracked(self):
        """Records with outgoing unresolved CONTRADICTS edges are flagged."""
        rec_a = _make_record("rec-a", content="Use tabs for indentation")
        rec_b = _make_record("rec-b", content="Use spaces for indentation")

        edges = [_make_edge("rec-a", "rec-b", EdgeType.CONTRADICTS, resolution_id=None)]
        kg = FakeKGStore(edges)

        prioritizer = ExpertisePrioritizer()
        prioritizer.prioritize([rec_a, rec_b], kg_store=kg)

        assert "rec-a" in prioritizer._contradiction_ids

    def test_resolved_contradictions_not_flagged(self):
        """Resolved CONTRADICTS edges should not flag the record."""
        rec_a = _make_record("rec-a", content="Use tabs")
        rec_b = _make_record("rec-b", content="Use spaces")

        edges = [_make_edge("rec-a", "rec-b", EdgeType.CONTRADICTS, resolution_id="res-1")]
        kg = FakeKGStore(edges)

        prioritizer = ExpertisePrioritizer()
        prioritizer.prioritize([rec_a, rec_b], kg_store=kg)

        assert "rec-a" not in prioritizer._contradiction_ids

    def test_no_kg_store_preserves_all_records(self):
        """Without KG store, no records are superseded or annotated."""
        records = [_make_record(f"r-{i}") for i in range(3)]

        prioritizer = ExpertisePrioritizer()
        result = prioritizer.prioritize(records, kg_store=None)

        assert result.records_included == 3
        assert prioritizer._contradiction_ids == set()
        assert prioritizer._qualifying_notes == {}


class TestRecencyBoost:
    def test_boost_within_7_days(self):
        p = ExpertisePrioritizer()
        assert p._recency_boost(_utcnow() - timedelta(days=3)) == 5

    def test_boost_within_30_days(self):
        p = ExpertisePrioritizer()
        assert p._recency_boost(_utcnow() - timedelta(days=15)) == 3

    def test_boost_within_90_days(self):
        p = ExpertisePrioritizer()
        assert p._recency_boost(_utcnow() - timedelta(days=60)) == 1

    def test_no_boost_beyond_90_days(self):
        p = ExpertisePrioritizer()
        assert p._recency_boost(_utcnow() - timedelta(days=120)) == 0


class TestPrimeFormatterPrompt:
    def test_format_prompt_with_contradiction_and_qualifying(self):
        rec = _make_record("r-1", type_=ExpertiseType.CONVENTION, content="Use Black formatter")
        result = PrimeResult(
            expertise=[rec],
            token_count=10,
            domains_covered=["python"],
            records_total=1,
            records_included=1,
            records_filtered_inactive=0,
        )

        formatter = PrimeFormatter()
        output = formatter.format_prompt(
            result,
            project="myproj",
            contradiction_ids={"r-1"},
            qualifying_notes={"r-1": ["r-2"]},
        )

        assert "[CONTESTED]" in output
        assert "[QUALIFIED by r-2]" in output
        assert "myproj" in output

    def test_format_prompt_failure_with_resolution(self):
        rec = _make_record(
            "r-f",
            type_=ExpertiseType.FAILURE,
            content="Memory leak in worker",
            resolution="Increase GC frequency",
        )
        result = PrimeResult(
            expertise=[rec],
            token_count=10,
            domains_covered=["infra"],
            records_total=1,
            records_included=1,
            records_filtered_inactive=0,
        )

        formatter = PrimeFormatter()
        output = formatter.format_prompt(result)
        assert "Fix: Increase GC frequency" in output

    def test_format_prompt_decision_with_rationale(self):
        rec = _make_record(
            "r-d",
            type_=ExpertiseType.DECISION,
            content="Use PostgreSQL",
            name="DB Choice",
        )
        object.__setattr__(rec, "rationale", "Better JSON support")
        result = PrimeResult(
            expertise=[rec],
            token_count=10,
            domains_covered=["arch"],
            records_total=1,
            records_included=1,
            records_filtered_inactive=0,
        )

        formatter = PrimeFormatter()
        output = formatter.format_prompt(result)
        assert "DB Choice" in output
        assert "Better JSON support" in output


class TestPrimeFormatterMarkdown:
    def test_format_markdown_with_annotations(self):
        rec = _make_record("r-1", type_=ExpertiseType.BOUNDARY, content="Never delete parquet files")
        result = PrimeResult(
            expertise=[rec],
            token_count=10,
            domains_covered=["safety"],
            records_total=1,
            records_included=1,
            records_filtered_inactive=0,
        )

        formatter = PrimeFormatter()
        output = formatter.format_markdown(
            result,
            contradiction_ids={"r-1"},
            qualifying_notes={"r-1": ["r-2"]},
        )

        assert "*(contested)*" in output
        assert "*(qualified by: r-2)*" in output
        assert "### Boundaries" in output
