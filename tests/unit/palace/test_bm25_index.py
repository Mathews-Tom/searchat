"""Tests for PalaceBM25Index."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import duckdb
import pytest

from searchat.models.domain import DistilledObject, FileTouched, Room
from searchat.palace.bm25_index import PalaceBM25Index
from searchat.palace.storage import PalaceStorage


@pytest.fixture
def populated_storage(tmp_path):
    """Storage with four objects and one room for BM25 IDF to work."""
    conn = duckdb.connect(":memory:")
    storage = PalaceStorage(data_dir=tmp_path, conn=conn)

    now = datetime(2026, 1, 1, 12, 0, 0)
    obj1 = DistilledObject(
        object_id="obj-1", project_id="proj-1", conversation_id="conv-1",
        ply_start=0, ply_end=5,
        files_touched=[FileTouched(path="src/auth.py", action="referenced")],
        exchange_core="Implemented JWT authentication",
        specific_context="Token expiry set to 15 minutes",
        created_at=now, exchange_at=now, embedding_id=0,
        distilled_text="Implemented JWT authentication\nToken expiry set to 15 minutes",
    )
    obj2 = DistilledObject(
        object_id="obj-2", project_id="proj-1", conversation_id="conv-2",
        ply_start=0, ply_end=3,
        files_touched=[FileTouched(path="src/database.py", action="referenced")],
        exchange_core="Added PostgreSQL connection pooling",
        specific_context="Pool size 20, timeout 30s",
        created_at=now, exchange_at=now, embedding_id=1,
        distilled_text="Added PostgreSQL connection pooling\nPool size 20, timeout 30s",
    )
    obj3 = DistilledObject(
        object_id="obj-3", project_id="proj-1", conversation_id="conv-3",
        ply_start=0, ply_end=4,
        files_touched=[FileTouched(path="src/api.py", action="referenced")],
        exchange_core="Refactored REST endpoints for versioning",
        specific_context="Added /v2/ prefix to all routes",
        created_at=now, exchange_at=now, embedding_id=2,
        distilled_text="Refactored REST endpoints for versioning\nAdded /v2/ prefix to all routes",
    )
    obj4 = DistilledObject(
        object_id="obj-4", project_id="proj-1", conversation_id="conv-4",
        ply_start=0, ply_end=6,
        files_touched=[FileTouched(path="src/cache.py", action="referenced")],
        exchange_core="Configured Redis caching layer",
        specific_context="TTL 300 seconds for session data",
        created_at=now, exchange_at=now, embedding_id=3,
        distilled_text="Configured Redis caching layer\nTTL 300 seconds for session data",
    )

    room = Room(
        room_id="room-1", room_type="concept", room_key="auth",
        room_label="Authentication", project_id="proj-1",
        created_at=now, updated_at=now, object_count=1,
    )

    from searchat.models.domain import RoomObject
    junction = RoomObject(
        room_id="room-1", object_id="obj-1", relevance=0.9, placed_at=now,
    )

    storage.store_distillation_results([obj1, obj2, obj3, obj4], [room], [junction])
    return storage


class TestBM25Index:
    def test_build_from_storage(self, populated_storage):
        index = PalaceBM25Index()
        count = index.build_from_storage(populated_storage)
        assert count == 4
        assert index.size == 4

    def test_search_returns_results(self, populated_storage):
        index = PalaceBM25Index()
        index.build_from_storage(populated_storage)

        results = index.search("JWT authentication")
        assert len(results) > 0
        # First result should be the auth object
        assert results[0][0] == "obj-1"
        assert results[0][1] > 0

    def test_search_database_query(self, populated_storage):
        index = PalaceBM25Index()
        index.build_from_storage(populated_storage)

        results = index.search("PostgreSQL connection")
        assert len(results) > 0
        assert results[0][0] == "obj-2"

    def test_search_no_results(self, populated_storage):
        index = PalaceBM25Index()
        index.build_from_storage(populated_storage)

        results = index.search("zzz_completely_unrelated_xyzzy")
        assert len(results) == 0

    def test_search_empty_index(self):
        index = PalaceBM25Index()
        results = index.search("anything")
        assert results == []

    def test_search_empty_query(self, populated_storage):
        index = PalaceBM25Index()
        index.build_from_storage(populated_storage)

        results = index.search("")
        assert results == []

    def test_includes_file_paths(self, populated_storage):
        index = PalaceBM25Index()
        index.build_from_storage(populated_storage)

        results = index.search("auth.py")
        assert len(results) > 0
        assert results[0][0] == "obj-1"

    def test_includes_room_metadata(self, populated_storage):
        index = PalaceBM25Index()
        index.build_from_storage(populated_storage)

        results = index.search("Authentication")
        assert len(results) > 0
        # obj-1 is in "Authentication" room
        obj_ids = [r[0] for r in results]
        assert "obj-1" in obj_ids

    def test_empty_storage(self, tmp_path):
        conn = duckdb.connect(":memory:")
        storage = PalaceStorage(data_dir=tmp_path, conn=conn)
        index = PalaceBM25Index()
        count = index.build_from_storage(storage)
        assert count == 0
        assert index.size == 0
