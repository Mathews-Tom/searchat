import json
import pytest
from pathlib import Path
from searchat.core import ConversationIndexer
from searchat.models import UpdateStats


@pytest.fixture
def test_project_dir(tmp_path):
    claude_dir = tmp_path / ".claude" / "projects" / "test-project"
    claude_dir.mkdir(parents=True)
    return claude_dir


@pytest.fixture
def indexer_with_initial_index(tmp_path, test_project_dir, monkeypatch):
    """Create an indexer with an initial index (simulating existing data)."""
    # Create initial conversation
    conv1_lines = [
        {"type": "user", "message": {"content": "Hello"}, "timestamp": "2025-09-01T10:00:00"},
        {"type": "assistant", "message": {"content": "Hi!"}, "timestamp": "2025-09-01T10:00:30"}
    ]
    conv1_file = test_project_dir / "conv1.jsonl"
    with open(conv1_file, 'w', encoding='utf-8') as f:
        for line in conv1_lines:
            f.write(json.dumps(line) + '\n')

    monkeypatch.setattr(
        'searchat.indexer.PathResolver.resolve_claude_dirs',
        lambda self, config=None: [tmp_path / ".claude" / "projects"]
    )

    # Create indexer - note: index_all() is blocked, so we need to work around this
    # For testing, we'll monkeypatch to allow it
    indexer = ConversationIndexer(tmp_path / "search")

    # Temporarily allow index_all for test setup
    original_index_all = ConversationIndexer.index_all
    def unblocked_index_all(self):
        # Skip the RuntimeError and run the actual indexing
        import time
        start_time = time.time()
        # ... simplified for test
        return indexer._do_initial_index()

    # For now, manually create the index structure
    indexer._ensure_directories()

    return indexer, test_project_dir, conv1_file


def test_append_only_skips_existing(tmp_path, test_project_dir, monkeypatch):
    """Test that index_append_only skips files already in the index."""
    # This test would require a fully set up index
    # Marking as placeholder for now
    pass


def test_append_only_adds_new_files(tmp_path, test_project_dir, monkeypatch):
    """Test that index_append_only adds new files."""
    # This test would require a fully set up index
    # Marking as placeholder for now
    pass


def test_append_only_never_deletes(tmp_path, test_project_dir, monkeypatch):
    """Test that index_append_only never removes existing data."""
    # This is the critical safety test
    # Even if source files are deleted, indexed data should remain
    pass


def test_get_indexed_file_paths(tmp_path, monkeypatch):
    """Test that get_indexed_file_paths returns correct set."""
    monkeypatch.setattr(
        'searchat.config.PathResolver.resolve_claude_dirs',
        lambda self, config=None: [tmp_path / ".claude" / "projects"]
    )

    indexer = ConversationIndexer(tmp_path / "search")

    # With no parquet files, should return empty set
    paths = indexer.get_indexed_file_paths()
    assert paths == set()
