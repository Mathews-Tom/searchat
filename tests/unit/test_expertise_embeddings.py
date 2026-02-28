"""Tests for ExpertiseEmbeddingIndex FAISS backend."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest

from searchat.expertise.embeddings import ExpertiseEmbeddingIndex, _EMBEDDING_DIM
from searchat.expertise.models import ExpertiseRecord, ExpertiseType


def _make_record(
    *,
    record_id: str = "exp_abc123",
    content: str = "Use uv for Python packages",
    domain: str = "python",
    type: ExpertiseType = ExpertiseType.CONVENTION,
) -> ExpertiseRecord:
    return ExpertiseRecord(id=record_id, type=type, domain=domain, content=content)


@pytest.fixture
def embedding_index(tmp_path: Path) -> ExpertiseEmbeddingIndex:
    return ExpertiseEmbeddingIndex(data_dir=tmp_path)


# ------------------------------------------------------------------
# Initialization
# ------------------------------------------------------------------


class TestInit:
    def test_creates_expertise_directory(self, tmp_path: Path) -> None:
        ExpertiseEmbeddingIndex(data_dir=tmp_path)
        assert (tmp_path / "expertise").is_dir()

    def test_creates_empty_faiss_index(self, embedding_index: ExpertiseEmbeddingIndex) -> None:
        assert embedding_index._index is not None
        assert embedding_index._index.ntotal == 0

    def test_initial_mappings_empty(self, embedding_index: ExpertiseEmbeddingIndex) -> None:
        assert embedding_index._record_to_vec == {}
        assert embedding_index._vec_to_record == {}
        assert embedding_index._next_id == 0

    def test_loads_existing_index(self, tmp_path: Path) -> None:
        """Create an index, save it, then load from disk."""
        idx1 = ExpertiseEmbeddingIndex(data_dir=tmp_path)
        record = _make_record(record_id="exp_load_test")
        idx1.add(record)
        assert idx1._index.ntotal == 1

        idx2 = ExpertiseEmbeddingIndex(data_dir=tmp_path)
        assert idx2._index.ntotal == 1
        assert "exp_load_test" in idx2._record_to_vec
        assert idx2._next_id == 1


# ------------------------------------------------------------------
# Add operations
# ------------------------------------------------------------------


class TestAdd:
    def test_add_single_record(self, embedding_index: ExpertiseEmbeddingIndex) -> None:
        record = _make_record()
        embedding_index.add(record)
        assert embedding_index._index.ntotal == 1
        assert record.id in embedding_index._record_to_vec

    def test_add_increments_next_id(self, embedding_index: ExpertiseEmbeddingIndex) -> None:
        embedding_index.add(_make_record(record_id="exp_001"))
        embedding_index.add(_make_record(record_id="exp_002"))
        assert embedding_index._next_id == 2

    def test_add_persists_to_disk(self, embedding_index: ExpertiseEmbeddingIndex) -> None:
        embedding_index.add(_make_record())
        assert embedding_index._faiss_path.exists()
        assert embedding_index._metadata_path.exists()

    def test_metadata_parquet_has_correct_schema(self, embedding_index: ExpertiseEmbeddingIndex) -> None:
        embedding_index.add(_make_record(record_id="exp_schema"))
        table = pq.read_table(embedding_index._metadata_path)
        assert "vector_id" in table.column_names
        assert "record_id" in table.column_names
        assert table.num_rows == 1
        assert table.column("record_id").to_pylist() == ["exp_schema"]

    def test_add_updates_bidirectional_mapping(self, embedding_index: ExpertiseEmbeddingIndex) -> None:
        record = _make_record(record_id="exp_bidir")
        embedding_index.add(record)
        vid = embedding_index._record_to_vec["exp_bidir"]
        assert embedding_index._vec_to_record[vid] == "exp_bidir"

    def test_vector_ids_are_sequential(self, embedding_index: ExpertiseEmbeddingIndex) -> None:
        embedding_index.add(_make_record(record_id="exp_seq0"))
        embedding_index.add(_make_record(record_id="exp_seq1"))
        assert embedding_index._record_to_vec["exp_seq0"] == 0
        assert embedding_index._record_to_vec["exp_seq1"] == 1


# ------------------------------------------------------------------
# Batch add
# ------------------------------------------------------------------


class TestAddBatch:
    def test_add_batch_empty_is_noop(self, embedding_index: ExpertiseEmbeddingIndex) -> None:
        embedding_index.add_batch([])
        assert embedding_index._index.ntotal == 0

    def test_add_batch_multiple_records(self, embedding_index: ExpertiseEmbeddingIndex) -> None:
        records = [
            _make_record(record_id="exp_b1", content="First"),
            _make_record(record_id="exp_b2", content="Second"),
            _make_record(record_id="exp_b3", content="Third"),
        ]
        embedding_index.add_batch(records)
        assert embedding_index._index.ntotal == 3
        assert len(embedding_index._record_to_vec) == 3

    def test_add_batch_persists(self, embedding_index: ExpertiseEmbeddingIndex) -> None:
        records = [_make_record(record_id=f"exp_p{i}", content=f"Item {i}") for i in range(5)]
        embedding_index.add_batch(records)
        table = pq.read_table(embedding_index._metadata_path)
        assert table.num_rows == 5

    def test_add_batch_assigns_sequential_ids(self, embedding_index: ExpertiseEmbeddingIndex) -> None:
        records = [_make_record(record_id=f"exp_bs{i}", content=f"Batch {i}") for i in range(3)]
        embedding_index.add_batch(records)
        assert embedding_index._record_to_vec["exp_bs0"] == 0
        assert embedding_index._record_to_vec["exp_bs1"] == 1
        assert embedding_index._record_to_vec["exp_bs2"] == 2


# ------------------------------------------------------------------
# Search
# ------------------------------------------------------------------


class TestSearch:
    def test_search_empty_index_returns_empty(self, embedding_index: ExpertiseEmbeddingIndex) -> None:
        results = embedding_index.search("anything")
        assert results == []

    def test_search_returns_record_ids_and_scores(self, embedding_index: ExpertiseEmbeddingIndex) -> None:
        embedding_index.add(_make_record(record_id="exp_s1", content="Python typing conventions"))
        results = embedding_index.search("Python typing conventions")
        assert len(results) >= 1
        record_id, score = results[0]
        assert isinstance(record_id, str)
        assert isinstance(score, float)

    def test_search_respects_limit(self, embedding_index: ExpertiseEmbeddingIndex) -> None:
        for i in range(10):
            embedding_index.add(_make_record(record_id=f"exp_lim{i}", content=f"Record number {i}"))
        results = embedding_index.search("Record", limit=3)
        assert len(results) <= 3

    def test_search_returns_known_record_ids(self, embedding_index: ExpertiseEmbeddingIndex) -> None:
        embedding_index.add(_make_record(record_id="exp_known", content="Known content"))
        results = embedding_index.search("Known content", limit=5)
        result_ids = {rid for rid, _ in results}
        # The only record in the index should be the one we added
        assert result_ids <= {"exp_known"}

    def test_find_similar_delegates_to_search(self, embedding_index: ExpertiseEmbeddingIndex) -> None:
        embedding_index.add(_make_record(record_id="exp_fs", content="Test content"))
        results = embedding_index.find_similar("Test content", limit=1)
        assert len(results) >= 1


# ------------------------------------------------------------------
# Remove
# ------------------------------------------------------------------


class TestRemove:
    def test_remove_existing_record(self, embedding_index: ExpertiseEmbeddingIndex) -> None:
        embedding_index.add(_make_record(record_id="exp_rm"))
        assert embedding_index._index.ntotal == 1
        embedding_index.remove("exp_rm")
        assert "exp_rm" not in embedding_index._record_to_vec
        assert embedding_index._index.ntotal == 0

    def test_remove_nonexistent_is_noop(self, embedding_index: ExpertiseEmbeddingIndex) -> None:
        embedding_index.remove("exp_nonexistent")
        assert embedding_index._index.ntotal == 0

    def test_remove_persists(self, embedding_index: ExpertiseEmbeddingIndex) -> None:
        embedding_index.add(_make_record(record_id="exp_rmp"))
        embedding_index.remove("exp_rmp")
        table = pq.read_table(embedding_index._metadata_path)
        assert table.num_rows == 0

    def test_remove_cleans_both_mappings(self, embedding_index: ExpertiseEmbeddingIndex) -> None:
        embedding_index.add(_make_record(record_id="exp_rmc"))
        vid = embedding_index._record_to_vec["exp_rmc"]
        embedding_index.remove("exp_rmc")
        assert "exp_rmc" not in embedding_index._record_to_vec
        assert vid not in embedding_index._vec_to_record

    def test_remove_one_of_many(self, embedding_index: ExpertiseEmbeddingIndex) -> None:
        embedding_index.add(_make_record(record_id="exp_keep1", content="Keep 1"))
        embedding_index.add(_make_record(record_id="exp_gone", content="Gone"))
        embedding_index.add(_make_record(record_id="exp_keep2", content="Keep 2"))
        embedding_index.remove("exp_gone")
        assert "exp_keep1" in embedding_index._record_to_vec
        assert "exp_keep2" in embedding_index._record_to_vec
        assert "exp_gone" not in embedding_index._record_to_vec


# ------------------------------------------------------------------
# Rebuild
# ------------------------------------------------------------------


class TestRebuild:
    def test_rebuild_from_empty(self, embedding_index: ExpertiseEmbeddingIndex) -> None:
        embedding_index.rebuild([])
        assert embedding_index._index.ntotal == 0
        assert embedding_index._next_id == 0

    def test_rebuild_replaces_existing(self, embedding_index: ExpertiseEmbeddingIndex) -> None:
        embedding_index.add(_make_record(record_id="exp_old", content="Old"))
        new_records = [
            _make_record(record_id="exp_new1", content="New 1"),
            _make_record(record_id="exp_new2", content="New 2"),
        ]
        embedding_index.rebuild(new_records)
        assert embedding_index._index.ntotal == 2
        assert "exp_old" not in embedding_index._record_to_vec
        assert "exp_new1" in embedding_index._record_to_vec
        assert "exp_new2" in embedding_index._record_to_vec

    def test_rebuild_resets_next_id(self, embedding_index: ExpertiseEmbeddingIndex) -> None:
        for i in range(5):
            embedding_index.add(_make_record(record_id=f"exp_r{i}", content=f"R {i}"))
        assert embedding_index._next_id == 5
        embedding_index.rebuild([_make_record(record_id="exp_rebuilt", content="Rebuilt")])
        assert embedding_index._next_id == 1

    def test_rebuild_persists(self, embedding_index: ExpertiseEmbeddingIndex) -> None:
        records = [_make_record(record_id=f"exp_rb{i}", content=f"Rebuilt {i}") for i in range(3)]
        embedding_index.rebuild(records)
        table = pq.read_table(embedding_index._metadata_path)
        assert table.num_rows == 3

    def test_rebuild_clears_old_mappings(self, embedding_index: ExpertiseEmbeddingIndex) -> None:
        embedding_index.add(_make_record(record_id="exp_stale", content="Stale"))
        old_vid = embedding_index._record_to_vec["exp_stale"]
        embedding_index.rebuild([])
        assert old_vid not in embedding_index._vec_to_record
        assert "exp_stale" not in embedding_index._record_to_vec


# ------------------------------------------------------------------
# Persistence round-trip
# ------------------------------------------------------------------


class TestPersistence:
    def test_full_round_trip(self, tmp_path: Path) -> None:
        """Add records, save, create new instance, verify loaded state."""
        idx = ExpertiseEmbeddingIndex(data_dir=tmp_path)
        records = [
            _make_record(record_id="exp_rt1", content="Round trip 1"),
            _make_record(record_id="exp_rt2", content="Round trip 2"),
        ]
        idx.add_batch(records)
        idx.remove("exp_rt1")

        idx2 = ExpertiseEmbeddingIndex(data_dir=tmp_path)
        assert "exp_rt2" in idx2._record_to_vec
        assert "exp_rt1" not in idx2._record_to_vec

    def test_faiss_file_written(self, embedding_index: ExpertiseEmbeddingIndex) -> None:
        embedding_index.add(_make_record())
        assert embedding_index._faiss_path.exists()

    def test_metadata_round_trip(self, tmp_path: Path) -> None:
        idx = ExpertiseEmbeddingIndex(data_dir=tmp_path)
        idx.add(_make_record(record_id="exp_meta1"))
        idx.add(_make_record(record_id="exp_meta2", content="Different"))

        idx2 = ExpertiseEmbeddingIndex(data_dir=tmp_path)
        assert len(idx2._record_to_vec) == 2
        assert idx2._next_id == 2


# ------------------------------------------------------------------
# Index structure
# ------------------------------------------------------------------


class TestIndexStructure:
    def test_index_dimension(self, embedding_index: ExpertiseEmbeddingIndex) -> None:
        assert embedding_index._index is not None
        assert embedding_index._index.d == _EMBEDDING_DIM

    def test_embedding_dimension_is_384(self) -> None:
        assert _EMBEDDING_DIM == 384

    def test_paths_under_expertise_dir(self, embedding_index: ExpertiseEmbeddingIndex) -> None:
        assert embedding_index._faiss_path.name == "expertise_embeddings.faiss"
        assert embedding_index._metadata_path.name == "expertise_embeddings.metadata.parquet"
        assert embedding_index._faiss_path.parent == embedding_index._expertise_dir
