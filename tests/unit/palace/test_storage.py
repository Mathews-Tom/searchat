"""Tests for PalaceStorage DuckDB backend."""
from __future__ import annotations

from datetime import datetime

import duckdb
import pytest

from searchat.models.domain import DistilledObject, FileTouched, Room, RoomObject
from searchat.palace.storage import PalaceStorage


@pytest.fixture
def storage(tmp_path):
    """Create an in-memory PalaceStorage for testing."""
    conn = duckdb.connect(":memory:")
    return PalaceStorage(data_dir=tmp_path, conn=conn)


def _make_object(
    object_id: str = "obj-1",
    conversation_id: str = "conv-1",
    project_id: str = "proj-1",
    ply_start: int = 0,
    ply_end: int = 5,
) -> DistilledObject:
    now = datetime(2026, 1, 1, 12, 0, 0)
    return DistilledObject(
        object_id=object_id,
        project_id=project_id,
        conversation_id=conversation_id,
        ply_start=ply_start,
        ply_end=ply_end,
        files_touched=[FileTouched(path="src/main.py", action="referenced")],
        exchange_core="Fixed the login bug",
        specific_context="Error 401 on /api/auth",
        created_at=now,
        exchange_at=now,
        embedding_id=0,
        distilled_text="Fixed the login bug\nError 401 on /api/auth",
    )


def _make_room(
    room_id: str = "room-1",
    project_id: str = "proj-1",
) -> Room:
    now = datetime(2026, 1, 1, 12, 0, 0)
    return Room(
        room_id=room_id,
        room_type="concept",
        room_key="auth",
        room_label="Authentication",
        project_id=project_id,
        created_at=now,
        updated_at=now,
        object_count=1,
    )


def _make_junction(
    room_id: str = "room-1",
    object_id: str = "obj-1",
) -> RoomObject:
    return RoomObject(
        room_id=room_id,
        object_id=object_id,
        relevance=0.9,
        placed_at=datetime(2026, 1, 1, 12, 0, 0),
    )


class TestPalaceStorageInit:
    def test_creates_tables(self, storage):
        tables = storage.conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
        table_names = {t[0] for t in tables}
        assert "objects" in table_names
        assert "rooms" in table_names
        assert "room_objects" in table_names
        assert "skipped_conversations" in table_names


class TestStoreAndRetrieve:
    def test_store_and_get_object(self, storage):
        obj = _make_object()
        room = _make_room()
        junction = _make_junction()

        storage.store_distillation_results([obj], [room], [junction])

        retrieved = storage.get_object_by_id("obj-1")
        assert retrieved.object_id == "obj-1"
        assert retrieved.exchange_core == "Fixed the login bug"
        assert len(retrieved.files_touched) == 1
        assert retrieved.files_touched[0].path == "src/main.py"

    def test_get_object_not_found(self, storage):
        with pytest.raises(KeyError, match="Object not found"):
            storage.get_object_by_id("nonexistent")

    def test_get_objects_by_ids(self, storage):
        obj1 = _make_object("obj-1", ply_start=0, ply_end=5)
        obj2 = _make_object("obj-2", ply_start=6, ply_end=10)
        storage.store_distillation_results([obj1, obj2], [], [])

        results = storage.get_objects_by_ids(["obj-1", "obj-2"])
        assert len(results) == 2

    def test_get_objects_by_ids_empty(self, storage):
        assert storage.get_objects_by_ids([]) == []

    def test_get_all_objects(self, storage):
        obj = _make_object()
        storage.store_distillation_results([obj], [], [])

        all_objs = storage.get_all_objects()
        assert len(all_objs) == 1

    def test_get_all_objects_filtered(self, storage):
        obj1 = _make_object("obj-1", project_id="proj-1", ply_start=0, ply_end=5)
        obj2 = _make_object("obj-2", project_id="proj-2", ply_start=6, ply_end=10)
        storage.store_distillation_results([obj1, obj2], [], [])

        results = storage.get_all_objects(project_id="proj-1")
        assert len(results) == 1
        assert results[0].project_id == "proj-1"


class TestRooms:
    def test_store_and_get_room(self, storage):
        obj = _make_object()
        room = _make_room()
        junction = _make_junction()
        storage.store_distillation_results([obj], [room], [junction])

        rooms = storage.get_all_rooms()
        assert len(rooms) == 1
        assert rooms[0].room_key == "auth"

    def test_find_rooms_by_keyword(self, storage):
        obj = _make_object()
        room = _make_room()
        junction = _make_junction()
        storage.store_distillation_results([obj], [room], [junction])

        found = storage.find_rooms_by_keyword("auth")
        assert len(found) == 1
        assert found[0].room_id == "room-1"

    def test_find_rooms_no_match(self, storage):
        obj = _make_object()
        room = _make_room()
        junction = _make_junction()
        storage.store_distillation_results([obj], [room], [junction])

        found = storage.find_rooms_by_keyword("zzz_nonexistent")
        assert len(found) == 0

    def test_get_rooms_by_ids(self, storage):
        obj = _make_object()
        room = _make_room()
        junction = _make_junction()
        storage.store_distillation_results([obj], [room], [junction])

        found = storage.get_rooms_by_ids(["room-1"])
        assert len(found) == 1

    def test_get_rooms_by_ids_empty(self, storage):
        assert storage.get_rooms_by_ids([]) == []

    def test_get_rooms_for_object(self, storage):
        obj = _make_object()
        room = _make_room()
        junction = _make_junction()
        storage.store_distillation_results([obj], [room], [junction])

        rooms = storage.get_rooms_for_object("obj-1")
        assert len(rooms) == 1
        assert rooms[0].room_key == "auth"

    def test_get_objects_in_room(self, storage):
        obj = _make_object()
        room = _make_room()
        junction = _make_junction()
        storage.store_distillation_results([obj], [room], [junction])

        objects = storage.get_objects_in_room("room-1")
        assert len(objects) == 1
        assert objects[0].object_id == "obj-1"

    def test_get_all_rooms_filtered(self, storage):
        obj = _make_object()
        room = _make_room()
        junction = _make_junction()
        storage.store_distillation_results([obj], [room], [junction])

        results = storage.get_all_rooms(project_id="proj-1")
        assert len(results) == 1

        results = storage.get_all_rooms(project_id="proj-999")
        assert len(results) == 0


class TestRoomObjectPairs:
    def test_get_all_pairs(self, storage):
        obj = _make_object()
        room = _make_room()
        junction = _make_junction()
        storage.store_distillation_results([obj], [room], [junction])

        pairs = storage.get_room_object_pairs()
        assert len(pairs) == 1

    def test_get_pairs_filtered(self, storage):
        obj = _make_object()
        room = _make_room()
        junction = _make_junction()
        storage.store_distillation_results([obj], [room], [junction])

        pairs = storage.get_room_object_pairs(["obj-1"])
        assert len(pairs) == 1

        pairs = storage.get_room_object_pairs(["nonexistent"])
        assert len(pairs) == 0


class TestSkippedConversations:
    def test_mark_and_get_skipped(self, storage):
        storage.mark_conversation_skipped("conv-x", "no_valid_exchanges")

        skipped = storage.get_skipped_conversation_ids()
        assert "conv-x" in skipped

    def test_clear_llm_error_skips(self, storage):
        storage.mark_conversation_skipped("conv-a", "llm_error: timeout")
        storage.mark_conversation_skipped("conv-b", "no_valid_exchanges")

        cleared = storage.clear_llm_error_skips()
        assert cleared == 1

        skipped = storage.get_skipped_conversation_ids()
        assert "conv-a" not in skipped
        assert "conv-b" in skipped


class TestDedup:
    def test_get_existing_object_keys(self, storage):
        obj = _make_object()
        storage.store_distillation_results([obj], [], [])

        keys = storage.get_existing_object_keys("conv-1")
        assert ("conv-1", 0, 5) in keys

    def test_get_existing_object_keys_all(self, storage):
        obj = _make_object()
        storage.store_distillation_results([obj], [], [])

        keys = storage.get_existing_object_keys()
        assert len(keys) == 1

    def test_get_distilled_conversation_ids(self, storage):
        obj = _make_object()
        storage.store_distillation_results([obj], [], [])

        ids = storage.get_distilled_conversation_ids()
        assert "conv-1" in ids


class TestStats:
    def test_get_stats(self, storage):
        obj = _make_object()
        room = _make_room()
        junction = _make_junction()
        storage.store_distillation_results([obj], [room], [junction])

        stats = storage.get_stats()
        assert stats["total_objects"] == 1
        assert stats["total_rooms"] == 1
        assert stats["total_conversations"] == 1


class TestChangeToken:
    def test_change_token_increments(self, storage):
        initial = storage.get_change_token()
        obj = _make_object()
        storage.store_distillation_results([obj], [], [])
        assert storage.get_change_token() == initial + 1


class TestDuplicateHandling:
    def test_duplicate_object_ignored(self, storage):
        obj = _make_object()
        storage.store_distillation_results([obj], [], [])
        storage.store_distillation_results([obj], [], [])

        all_objs = storage.get_all_objects()
        assert len(all_objs) == 1

    def test_duplicate_room_updates(self, storage):
        room1 = _make_room()
        room1.object_count = 1
        obj = _make_object()
        storage.store_distillation_results([obj], [room1], [])

        room2 = _make_room()
        room2.object_count = 5
        storage.store_distillation_results([], [room2], [])

        rooms = storage.get_all_rooms()
        assert len(rooms) == 1
        assert rooms[0].object_count == 5
