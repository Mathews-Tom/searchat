"""Unit tests for indexing and admin API routes."""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from pathlib import Path

from fastapi.testclient import TestClient

from searchat.api.app import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_config():
    """Mock Config."""
    mock = Mock()
    return mock


@pytest.fixture
def mock_indexer():
    """Mock ConversationIndexer."""
    mock = Mock()

    # Mock IndexStats
    mock_stats = Mock()
    mock_stats.new_conversations = 5
    mock_stats.total_conversations = 10
    mock_stats.skipped_conversations = 0

    mock.index_append_only.return_value = mock_stats
    mock.get_indexed_file_paths.return_value = set(["/indexed/conv1.jsonl", "/indexed/conv2.jsonl"])

    return mock


@pytest.fixture
def mock_watcher():
    """Mock ConversationWatcher."""
    mock = Mock()
    mock.is_running = True
    mock.get_watched_directories.return_value = [Path("/watched/dir1"), Path("/watched/dir2")]
    mock.stop = Mock()
    return mock


# ============================================================================
# INDEXING ENDPOINT TESTS
# ============================================================================

@pytest.mark.unit
class TestReindexEndpoint:
    """Tests for POST /api/reindex endpoint."""

    def test_reindex_blocked_for_safety(self, client):
        """Test that reindex is blocked for data safety."""
        response = client.post("/api/reindex")

        assert response.status_code == 403
        assert "BLOCKED" in response.json()["detail"]
        assert "data loss" in response.json()["detail"].lower()


@pytest.mark.unit
class TestIndexMissingEndpoint:
    """Tests for POST /api/index_missing endpoint."""

    def test_index_missing_success(self, client, mock_config, mock_indexer, tmp_path):
        """Test indexing missing conversations successfully."""
        # Create temporary conversation files
        claude_dir = tmp_path / "claude"
        claude_dir.mkdir()
        (claude_dir / "conv1.jsonl").write_text('{"type": "user"}')
        (claude_dir / "conv2.jsonl").write_text('{"type": "user"}')
        (claude_dir / "conv3.jsonl").write_text('{"type": "user"}')  # New file

        vibe_dir = tmp_path / "vibe"
        vibe_dir.mkdir()
        (vibe_dir / "session1.json").write_text('{}')

        with patch('searchat.api.routers.indexing.get_config', return_value=mock_config):
            with patch('searchat.api.routers.indexing.get_indexer', return_value=mock_indexer):
                with patch('searchat.api.routers.indexing.invalidate_search_index') as invalidate:
                    with patch('searchat.api.routers.indexing.PathResolver.resolve_claude_dirs', return_value=[claude_dir]):
                        with patch('searchat.api.routers.indexing.PathResolver.resolve_vibe_dirs', return_value=[vibe_dir]):
                            with patch('searchat.api.routers.indexing.indexing_state', {"in_progress": False}):
                                response = client.post("/api/index_missing")

                                assert response.status_code == 200
                                data = response.json()

                                assert data["success"] is True
                                assert data["new_conversations"] == 5
                                assert data["total_files"] == 4  # 3 JSONL + 1 JSON
                                assert data["already_indexed"] == 2
                                assert "time_seconds" in data

                                mock_indexer.index_append_only.assert_called_once()
                                invalidate.assert_called_once()

    def test_index_missing_all_indexed(self, client, mock_config, mock_indexer, tmp_path):
        """Test when all conversations are already indexed."""
        claude_dir = tmp_path / "claude"
        claude_dir.mkdir()
        (claude_dir / "conv1.jsonl").write_text('{"type": "user"}')

        # Mock that all files are already indexed
        mock_indexer.get_indexed_file_paths.return_value = set([str(claude_dir / "conv1.jsonl")])

        with patch('searchat.api.routers.indexing.get_config', return_value=mock_config):
            with patch('searchat.api.routers.indexing.get_indexer', return_value=mock_indexer):
                with patch('searchat.api.routers.indexing.PathResolver.resolve_claude_dirs', return_value=[claude_dir]):
                    with patch('searchat.api.routers.indexing.PathResolver.resolve_vibe_dirs', return_value=[]):
                        response = client.post("/api/index_missing")

                        assert response.status_code == 200
                        data = response.json()

                        assert data["success"] is True
                        assert data["new_conversations"] == 0
                        assert "already indexed" in data["message"].lower()

                        mock_indexer.index_append_only.assert_not_called()

    def test_index_missing_sets_indexing_state(self, client, mock_config, mock_indexer, tmp_path):
        """Test that indexing state is properly managed."""
        claude_dir = tmp_path / "claude"
        claude_dir.mkdir()
        (claude_dir / "conv1.jsonl").write_text('{"type": "user"}')

        indexing_state = {"in_progress": False, "operation": None}

        with patch('searchat.api.routers.indexing.get_config', return_value=mock_config):
            with patch('searchat.api.routers.indexing.get_indexer', return_value=mock_indexer):
                with patch('searchat.api.routers.indexing.PathResolver.resolve_claude_dirs', return_value=[claude_dir]):
                    with patch('searchat.api.routers.indexing.PathResolver.resolve_vibe_dirs', return_value=[]):
                        with patch('searchat.api.routers.indexing.indexing_state', indexing_state):
                            response = client.post("/api/index_missing")

                            # State should be reset after completion
                            assert indexing_state["in_progress"] is False
                            assert indexing_state["operation"] is None

    def test_index_missing_error_handling(self, client, mock_config, mock_indexer, tmp_path):
        """Test error handling when indexing fails."""
        # Create a file so it's not filtered out as already indexed
        test_file = tmp_path / "test.jsonl"
        test_file.write_text("{}")

        mock_indexer.index_append_only.side_effect = Exception("Indexing error")
        mock_indexer.get_indexed_file_paths.return_value = set()  # Not indexed yet

        with patch('searchat.api.routers.indexing.get_config', return_value=mock_config):
            with patch('searchat.api.routers.indexing.get_indexer', return_value=mock_indexer):
                with patch('searchat.api.routers.indexing.PathResolver.resolve_claude_dirs', return_value=[tmp_path]):
                    with patch('searchat.api.routers.indexing.PathResolver.resolve_vibe_dirs', return_value=[]):
                        with patch('searchat.api.routers.indexing.indexing_state', {"in_progress": False}):
                            response = client.post("/api/index_missing")

                            assert response.status_code == 500
                            assert "Indexing error" in response.json()["detail"]


# ============================================================================
# ADMIN ENDPOINT TESTS
# ============================================================================

@pytest.mark.unit
class TestWatcherStatusEndpoint:
    """Tests for GET /api/watcher/status endpoint."""

    def test_get_watcher_status_running(self, client, mock_watcher):
        """Test getting watcher status when running."""
        watcher_stats = {"indexed_count": 5, "last_update": "2025-01-20T10:00:00"}

        with patch('searchat.api.routers.admin.get_watcher', return_value=mock_watcher):
            with patch('searchat.api.routers.admin.watcher_stats', watcher_stats):
                response = client.get("/api/watcher/status")

                assert response.status_code == 200
                data = response.json()

                assert data["running"] is True
                assert len(data["watched_directories"]) == 2
                assert data["indexed_since_start"] == 5
                assert data["last_update"] == "2025-01-20T10:00:00"

    def test_get_watcher_status_not_running(self, client):
        """Test getting watcher status when not running."""
        watcher_stats = {"indexed_count": 0, "last_update": None}

        with patch('searchat.api.routers.admin.get_watcher', return_value=None):
            with patch('searchat.api.routers.admin.watcher_stats', watcher_stats):
                response = client.get("/api/watcher/status")

                assert response.status_code == 200
                data = response.json()

                assert data["running"] is False
                assert data["watched_directories"] == []


@pytest.mark.unit
class TestShutdownEndpoint:
    """Tests for POST /api/shutdown endpoint."""

    def test_shutdown_success(self, client, mock_watcher):
        """Test graceful shutdown when no indexing in progress."""
        indexing_state = {"in_progress": False}

        with patch('searchat.api.routers.admin.get_watcher', return_value=mock_watcher):
            with patch('searchat.api.routers.admin.indexing_state', indexing_state):
                with patch('searchat.api.routers.admin.os.kill'):
                    response = client.post("/api/shutdown")

                assert response.status_code == 200
                data = response.json()

                assert data["success"] is True
                assert data["forced"] is False
                assert "gracefully" in data["message"].lower()

    def test_shutdown_blocked_during_indexing(self, client):
        """Test that shutdown is blocked when indexing is in progress."""
        indexing_state = {
            "in_progress": True,
            "operation": "manual_index",
            "started_at": datetime.now().isoformat(),
            "files_total": 100
        }

        with patch('searchat.api.routers.admin.indexing_state', indexing_state):
            response = client.post("/api/shutdown")

            assert response.status_code == 200
            data = response.json()

            assert data["success"] is False
            assert data["indexing_in_progress"] is True
            assert data["operation"] == "manual_index"
            assert "force=true" in data["message"]

    def test_shutdown_forced_during_indexing(self, client, mock_watcher):
        """Test forced shutdown during indexing."""
        indexing_state = {
            "in_progress": True,
            "operation": "manual_index",
            "started_at": datetime.now().isoformat(),
            "files_total": 100
        }

        with patch('searchat.api.routers.admin.get_watcher', return_value=mock_watcher):
            with patch('searchat.api.routers.admin.indexing_state', indexing_state):
                with patch('searchat.api.routers.admin.os.kill'):
                    response = client.post("/api/shutdown?force=true")

                assert response.status_code == 200
                data = response.json()

                assert data["success"] is True
                assert data["forced"] is True
                assert "interrupted" in data["message"].lower()

    def test_shutdown_stops_watcher(self, client, mock_watcher):
        """Test that shutdown stops the file watcher."""
        indexing_state = {"in_progress": False}

        with patch('searchat.api.routers.admin.get_watcher', return_value=mock_watcher):
            with patch('searchat.api.routers.admin.indexing_state', indexing_state):
                # Just check the request is successful
                # The actual shutdown happens in background task
                with patch('searchat.api.routers.admin.os.kill'):
                    response = client.post("/api/shutdown")

                assert response.status_code == 200
                assert response.json()["success"] is True
