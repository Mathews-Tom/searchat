"""Unit tests for BookmarksService."""
from __future__ import annotations

import json
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from searchat.services.bookmarks import BookmarksService
from searchat.config import Config


@pytest.fixture
def mock_config(tmp_path):
    """Create mock config with temporary paths."""
    config = Mock(spec=Config)
    config.paths = Mock()
    config.paths.search_directory = str(tmp_path / ".searchat")
    return config


@pytest.fixture
def bookmarks_service(mock_config):
    """Create BookmarksService with mock config."""
    # Service will create directory and file in __init__ via _ensure_file()
    service = BookmarksService(mock_config)
    return service


def test_bookmarks_service_initialization(bookmarks_service):
    """Test BookmarksService initializes correctly."""
    assert bookmarks_service.bookmarks_file.exists()
    assert bookmarks_service.bookmarks_file.name == "bookmarks.json"


def test_load_bookmarks_empty(bookmarks_service):
    """Test loading bookmarks when file doesn't exist returns empty dict."""
    bookmarks = bookmarks_service._load_bookmarks()
    assert bookmarks == {}


def test_save_and_load_bookmarks(bookmarks_service):
    """Test saving and loading bookmarks."""
    test_bookmarks = {
        "conv-1": {
            "conversation_id": "conv-1",
            "added_at": "2026-01-28T10:00:00",
            "notes": "Important conversation"
        }
    }

    bookmarks_service._save_bookmarks(test_bookmarks)
    loaded = bookmarks_service._load_bookmarks()

    assert loaded == test_bookmarks


def test_add_bookmark(bookmarks_service):
    """Test adding a bookmark."""
    conv_id = "conv-123"
    notes = "Test bookmark"

    bookmark = bookmarks_service.add_bookmark(conv_id, notes)

    assert bookmark["conversation_id"] == conv_id
    assert bookmark["notes"] == notes
    assert "added_at" in bookmark

    # Verify it was saved
    bookmarks = bookmarks_service._load_bookmarks()
    assert conv_id in bookmarks
    assert bookmarks[conv_id]["notes"] == notes


def test_add_bookmark_without_notes(bookmarks_service):
    """Test adding a bookmark without notes."""
    conv_id = "conv-456"

    bookmark = bookmarks_service.add_bookmark(conv_id)

    assert bookmark["conversation_id"] == conv_id
    assert bookmark["notes"] == ""


def test_remove_bookmark(bookmarks_service):
    """Test removing a bookmark."""
    conv_id = "conv-789"

    # Add bookmark first
    bookmarks_service.add_bookmark(conv_id, "Test")

    # Verify it exists
    assert conv_id in bookmarks_service._load_bookmarks()

    # Remove it
    result = bookmarks_service.remove_bookmark(conv_id)

    assert result is True
    assert conv_id not in bookmarks_service._load_bookmarks()


def test_remove_nonexistent_bookmark(bookmarks_service):
    """Test removing a bookmark that doesn't exist."""
    result = bookmarks_service.remove_bookmark("nonexistent-conv")
    assert result is False


def test_get_bookmarks_empty(bookmarks_service):
    """Test getting bookmarks when none exist."""
    bookmarks = bookmarks_service.get_bookmarks()
    assert bookmarks == []


def test_get_bookmarks_sorted(bookmarks_service):
    """Test bookmarks are returned sorted by added_at descending."""
    # Add bookmarks with different timestamps
    conv1 = bookmarks_service.add_bookmark("conv-1", "First")

    # Sleep is not needed, we can manually set different timestamps
    bookmarks_service._save_bookmarks({
        "conv-1": {
            "conversation_id": "conv-1",
            "added_at": "2026-01-28T10:00:00",
            "notes": "First"
        },
        "conv-2": {
            "conversation_id": "conv-2",
            "added_at": "2026-01-28T11:00:00",
            "notes": "Second"
        },
        "conv-3": {
            "conversation_id": "conv-3",
            "added_at": "2026-01-28T09:00:00",
            "notes": "Third"
        }
    })

    bookmarks = bookmarks_service.get_bookmarks()

    # Should be sorted by added_at descending
    assert len(bookmarks) == 3
    assert bookmarks[0]["conversation_id"] == "conv-2"  # 11:00 (newest)
    assert bookmarks[1]["conversation_id"] == "conv-1"  # 10:00
    assert bookmarks[2]["conversation_id"] == "conv-3"  # 09:00 (oldest)


def test_update_bookmark_notes(bookmarks_service):
    """Test updating bookmark notes."""
    conv_id = "conv-update"

    # Add bookmark
    bookmarks_service.add_bookmark(conv_id, "Original notes")

    # Update notes
    updated = bookmarks_service.update_bookmark_notes(conv_id, "Updated notes")

    assert updated is not None
    assert updated["notes"] == "Updated notes"
    assert updated["conversation_id"] == conv_id

    # Verify persistence
    bookmarks = bookmarks_service._load_bookmarks()
    assert bookmarks[conv_id]["notes"] == "Updated notes"


def test_update_notes_nonexistent_bookmark(bookmarks_service):
    """Test updating notes for nonexistent bookmark returns None."""
    result = bookmarks_service.update_bookmark_notes("nonexistent", "Notes")
    assert result is None


def test_is_bookmarked(bookmarks_service):
    """Test checking if conversation is bookmarked."""
    conv_id = "conv-check"

    # Not bookmarked initially
    assert bookmarks_service.is_bookmarked(conv_id) is False

    # Add bookmark
    bookmarks_service.add_bookmark(conv_id)

    # Now it is bookmarked
    assert bookmarks_service.is_bookmarked(conv_id) is True


def test_json_file_corruption_handling(bookmarks_service):
    """Test handling of corrupted JSON file."""
    # Write invalid JSON
    bookmarks_service.bookmarks_file.write_text("invalid json {")

    # Should return empty dict and not crash
    bookmarks = bookmarks_service._load_bookmarks()
    assert bookmarks == {}


def test_multiple_bookmarks(bookmarks_service):
    """Test adding and managing multiple bookmarks."""
    # Add multiple bookmarks
    for i in range(5):
        bookmarks_service.add_bookmark(f"conv-{i}", f"Notes {i}")

    # Get all bookmarks
    bookmarks = bookmarks_service.get_bookmarks()
    assert len(bookmarks) == 5

    # Remove one
    bookmarks_service.remove_bookmark("conv-2")
    bookmarks = bookmarks_service.get_bookmarks()
    assert len(bookmarks) == 4
    assert not any(b["conversation_id"] == "conv-2" for b in bookmarks)


def test_bookmark_persistence_across_instances(mock_config):
    """Test bookmarks persist across service instances."""
    # Create first instance and add bookmark (service creates directory in __init__)
    service1 = BookmarksService(mock_config)
    service1.add_bookmark("conv-persist", "Persistent note")

    # Create second instance
    service2 = BookmarksService(mock_config)

    # Should be able to retrieve bookmark
    assert service2.is_bookmarked("conv-persist")
    bookmarks = service2.get_bookmarks()
    assert len(bookmarks) == 1
    assert bookmarks[0]["notes"] == "Persistent note"
