"""Unit tests for statistics and backup API routes."""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from pathlib import Path
from types import SimpleNamespace
import shutil

from fastapi import HTTPException
from fastapi.testclient import TestClient

from searchat.api.app import app
from searchat.api import state as api_state


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_duckdb_store_stats():
    """Mock DuckDBStore for stats endpoint."""
    from searchat.storage.unified_storage import IndexStatistics

    mock = Mock()
    mock.get_statistics.return_value = IndexStatistics(
        total_conversations=3,
        total_messages=30,
        avg_messages=10.0,
        total_projects=2,
        earliest_date="2025-01-01T00:00:00",
        latest_date="2025-01-20T00:00:00",
    )
    return mock


@pytest.fixture
def mock_backup_manager():
    """Mock BackupManager."""
    mock = Mock()
    mock.backup_dir = Path("/backups")

    # Mock BackupMetadata
    mock_metadata = Mock()
    mock_metadata.to_dict.return_value = {
        "backup_path": "/backups/backup_20250120_100000",
        "timestamp": "20250120_100000",
        "file_count": 5,
        "total_size_mb": 10.5
    }

    mock.create_backup.return_value = mock_metadata
    mock.create_incremental_backup.return_value = mock_metadata
    mock.list_backups.return_value = [mock_metadata]
    mock.restore_from_backup.return_value = None
    mock.get_backup_summary.return_value = {
        "name": "backup_20250120_100000",
        "backup_mode": "full",
        "encrypted": False,
        "parent_name": None,
        "chain_length": 1,
        "snapshot_browsable": True,
        "has_manifest": True,
        "valid": True,
        "errors": [],
    }
    mock.delete_backup.return_value = None
    mock.validate_backup_artifact.return_value = {
        "backup_name": "backup_20250120_100000",
        "valid": True,
        "errors": [],
    }
    mock.resolve_backup_chain.return_value = [
        "backup_20250120_090000",
        "backup_20250120_100000",
    ]

    return mock


# ============================================================================
# STATISTICS ENDPOINT TESTS
# ============================================================================

@pytest.mark.unit
class TestStatisticsEndpoint:
    """Tests for GET /api/statistics endpoint."""

    def test_get_statistics_success(self, client, mock_duckdb_store_stats):
        """Test getting index statistics."""
        with patch(
            'searchat.api.routers.stats.get_dataset_store',
            return_value=SimpleNamespace(snapshot_name=None, store=mock_duckdb_store_stats),
        ):
            with patch('searchat.api.routers.stats.api_state.stats_cache', None):
                response = client.get("/api/statistics")

            assert response.status_code == 200
            data = response.json()

            assert "total_conversations" in data
            assert "total_messages" in data
            assert "avg_messages" in data
            assert "total_projects" in data
            assert "earliest_date" in data
            assert "latest_date" in data

            # Verify values
            assert data["total_conversations"] == 3
            assert data["total_messages"] == 30  # 10 + 5 + 15
            assert data["avg_messages"] == 10.0  # 30 / 3
            assert data["total_projects"] == 2  # project-a, project-b
            assert data["earliest_date"] == "2025-01-01T00:00:00"
            assert data["latest_date"] == "2025-01-20T00:00:00"

    def test_get_statistics_single_conversation(self, client):
        """Test statistics with single conversation."""
        from searchat.storage.unified_storage import IndexStatistics

        mock_store = Mock()
        now = datetime.now().isoformat()
        mock_store.get_statistics.return_value = IndexStatistics(
            total_conversations=1,
            total_messages=10,
            avg_messages=10.0,
            total_projects=1,
            earliest_date=now,
            latest_date=now,
        )

        with patch(
            'searchat.api.routers.stats.get_dataset_store',
            return_value=SimpleNamespace(snapshot_name=None, store=mock_store),
        ):
            with patch('searchat.api.routers.stats.api_state.stats_cache', None):
                response = client.get("/api/statistics")

            assert response.status_code == 200
            data = response.json()

            assert data["total_conversations"] == 1
            assert data["total_messages"] == 10
            assert data["avg_messages"] == 10.0
            assert data["total_projects"] == 1

    def test_get_statistics_uses_cache(self, client):
        """Second call should return cached payload for active dataset."""
        from searchat.storage.unified_storage import IndexStatistics

        mock_store = Mock()
        mock_store.get_statistics.return_value = IndexStatistics(
            total_conversations=2,
            total_messages=20,
            avg_messages=10.0,
            total_projects=1,
            earliest_date="2025-01-01T00:00:00",
            latest_date="2025-01-02T00:00:00",
        )

        with patch(
            'searchat.api.routers.stats.get_dataset_store',
            return_value=SimpleNamespace(snapshot_name=None, store=mock_store),
        ):
            with patch('searchat.api.routers.stats.api_state.stats_cache', None):
                first = client.get("/api/statistics")
                second = client.get("/api/statistics")

        assert first.status_code == 200
        assert second.status_code == 200
        assert mock_store.get_statistics.call_count == 1

    def test_get_statistics_snapshot_uses_dataset_store(self, client, mock_duckdb_store_stats):
        """Snapshot requests should bypass stats_cache and use get_duckdb_store_for."""
        with patch(
            'searchat.api.routers.stats.get_dataset_store',
            return_value=SimpleNamespace(
                search_dir=Path('/tmp/snap'),
                snapshot_name='snap',
                store=mock_duckdb_store_stats,
            ),
        ) as get_store:
            resp = client.get("/api/statistics?snapshot=backup_20250101_000000")

        assert resp.status_code == 200
        get_store.assert_called_once()

    def test_get_statistics_snapshot_not_found_returns_404(self, client):
        with patch(
            'searchat.api.routers.stats.get_dataset_store',
            side_effect=HTTPException(status_code=404, detail="Snapshot not found"),
        ):
            resp = client.get("/api/statistics?snapshot=missing")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Snapshot not found"

    def test_get_statistics_snapshot_invalid_returns_400(self, client):
        with patch(
            'searchat.api.routers.stats.get_dataset_store',
            side_effect=HTTPException(status_code=400, detail="Invalid snapshot name"),
        ):
            resp = client.get("/api/statistics?snapshot=../nope")
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Invalid snapshot name"


# ============================================================================
# BACKUP ENDPOINT TESTS
# ============================================================================

@pytest.mark.unit
class TestCreateBackupEndpoint:
    """Tests for POST /api/backup/create endpoint."""

    def test_create_backup_success(self, client, mock_backup_manager):
        """Test creating a backup successfully."""
        with patch('searchat.api.routers.backup.get_backup_manager', return_value=mock_backup_manager):
            response = client.post("/api/backup/create")

            assert response.status_code == 200
            data = response.json()

            assert list(data) == ["success", "backup", "message"]
            assert data["success"] is True
            assert "Backup created" in data["message"]

            mock_backup_manager.create_backup.assert_called_once_with(backup_name=None, encrypted=False)

    def test_create_backup_with_name(self, client, mock_backup_manager):
        """Test creating a backup with custom name."""
        with patch('searchat.api.routers.backup.get_backup_manager', return_value=mock_backup_manager):
            response = client.post("/api/backup/create?backup_name=my_backup")

            assert response.status_code == 200
            mock_backup_manager.create_backup.assert_called_once_with(backup_name="my_backup", encrypted=False)

    def test_create_backup_error(self, client, mock_backup_manager):
        """Test error handling when backup fails."""
        mock_backup_manager.create_backup.side_effect = Exception("Disk full")

        with patch('searchat.api.routers.backup.get_backup_manager', return_value=mock_backup_manager):
            response = client.post("/api/backup/create")

            assert response.status_code == 500
            assert response.json()["detail"] == "Internal server error"


@pytest.mark.unit
class TestCreateIncrementalBackupEndpoint:
    """Tests for POST /api/backup/incremental/create endpoint."""

    def test_create_incremental_backup_success(self, client, mock_backup_manager):
        with patch('searchat.api.routers.backup.get_backup_manager', return_value=mock_backup_manager):
            resp = client.post("/api/backup/incremental/create?parent=backup_20250120_100000")

        assert resp.status_code == 200
        data = resp.json()
        assert list(data) == ["success", "backup", "message"]
        assert data["success"] is True
        assert "backup" in data
        mock_backup_manager.create_incremental_backup.assert_called_once_with(
            parent_name="backup_20250120_100000",
            backup_name=None,
            encrypted=False,
        )

    def test_create_incremental_backup_rejects_snapshot_mode(self, client, mock_backup_manager):
        with patch('searchat.api.routers.backup.get_backup_manager', return_value=mock_backup_manager):
            resp = client.post(
                "/api/backup/incremental/create?parent=backup_20250120_100000&snapshot=backup_20250101_000000"
            )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Backup operations are disabled in snapshot mode"


@pytest.mark.unit
class TestListBackupsEndpoint:
    """Tests for GET /api/backup/list endpoint."""

    def test_list_backups_success(self, client, mock_backup_manager):
        """Test listing all backups."""
        with patch('searchat.api.routers.backup.get_backup_manager', return_value=mock_backup_manager):
            response = client.get("/api/backup/list")

            assert response.status_code == 200
            data = response.json()

            assert list(data) == ["backups", "total", "backup_directory"]
            assert data["total"] == 1
            assert len(data["backups"]) == 1
            assert data["backups"][0]["valid"] is True
            assert data["backups"][0]["errors"] == []

    def test_list_backups_includes_invalid_summary_state(self, client, mock_backup_manager):
        mock_backup_manager.get_backup_summary.return_value = {
            "name": "backup_20250120_100000",
            "backup_mode": "incremental",
            "encrypted": False,
            "parent_name": "backup_20250120_090000",
            "chain_length": 0,
            "snapshot_browsable": False,
            "has_manifest": True,
            "valid": False,
            "errors": ["Backup manifest missing: backup_20250120_090000"],
        }

        with patch('searchat.api.routers.backup.get_backup_manager', return_value=mock_backup_manager):
            response = client.get("/api/backup/list")

        assert response.status_code == 200
        data = response.json()
        assert data["backups"][0]["valid"] is False
        assert data["backups"][0]["snapshot_browsable"] is False
        assert data["backups"][0]["backup_mode"] == "incremental"
        assert data["backups"][0]["errors"] == ["Backup manifest missing: backup_20250120_090000"]

    def test_list_backups_fixture_bundle_exposes_contract_health(self, client, tmp_path):
        from searchat.services.backup import BackupManager

        fixture = Path("tests/fixtures/storage/backup_contract_bundle")
        shutil.copytree(fixture, tmp_path, dirs_exist_ok=True)
        manager = BackupManager(tmp_path)

        with patch("searchat.api.routers.backup.get_backup_manager", return_value=manager):
            response = client.get("/api/backup/list")

        assert response.status_code == 200
        data = response.json()
        entries = {entry["name"]: entry for entry in data["backups"]}

        assert entries["legacy_plaintext_full"]["valid"] is True
        assert entries["legacy_plaintext_full"]["has_manifest"] is False
        assert entries["legacy_plaintext_full"]["snapshot_browsable"] is True

        assert entries["invalid_manifest_full"]["valid"] is False
        assert entries["invalid_manifest_full"]["backup_mode"] == "unknown"
        assert any("manifest version mismatch" in error.lower() for error in entries["invalid_manifest_full"]["errors"])

        assert entries["broken_chain_child"]["valid"] is False
        assert entries["broken_chain_child"]["backup_mode"] == "incremental"
        assert any("Backup manifest missing" in error for error in entries["broken_chain_child"]["errors"])

        assert entries["mixed_version_metadata_full"]["valid"] is True
        assert entries["mixed_version_metadata_full"]["backup_type"] == "unknown"
        assert entries["mixed_version_metadata_full"]["snapshot_browsable"] is True


@pytest.mark.unit
class TestValidateBackupEndpoint:
    """Tests for GET /api/backup/validate/{backup_name} endpoint."""

    def test_validate_backup_success(self, client, mock_backup_manager):
        with patch('searchat.api.routers.backup.get_backup_manager', return_value=mock_backup_manager):
            resp = client.get("/api/backup/validate/backup_20250120_100000")
        assert resp.status_code == 200
        data = resp.json()
        assert list(data) == ["backup_name", "valid", "errors"]
        assert data["valid"] is True
        mock_backup_manager.validate_backup_artifact.assert_called_once_with(
            "backup_20250120_100000",
            verify_hashes=False,
        )

    def test_validate_backup_reports_unavailable_contract(self, client):
        manager = SimpleNamespace(backup_dir=Path("/backups"))
        with patch('searchat.api.routers.backup.get_backup_manager', return_value=manager):
            resp = client.get("/api/backup/validate/backup_20250120_100000")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Backup validation is not available"


@pytest.mark.unit
class TestGetBackupChainEndpoint:
    """Tests for GET /api/backup/chain/{backup_name} endpoint."""

    def test_get_backup_chain_success(self, client, mock_backup_manager):
        mock_backup_manager.inspect_backup_chain.return_value = {
            "backup_name": "backup_20250120_100000",
            "chain": ["backup_20250120_090000", "backup_20250120_100000"],
            "chain_length": 2,
            "valid": True,
            "errors": [],
        }
        with patch('searchat.api.routers.backup.get_backup_manager', return_value=mock_backup_manager):
            resp = client.get("/api/backup/chain/backup_20250120_100000")

        assert resp.status_code == 200
        data = resp.json()
        assert list(data) == ["backup_name", "chain", "chain_length", "valid", "errors"]
        assert data["backup_name"] == "backup_20250120_100000"
        assert data["chain_length"] == 2
        assert data["chain"] == ["backup_20250120_090000", "backup_20250120_100000"]
        assert data["valid"] is True
        assert data["errors"] == []
        mock_backup_manager.inspect_backup_chain.assert_called_once_with("backup_20250120_100000")

    def test_get_backup_chain_reports_unavailable_contract(self, client):
        manager = SimpleNamespace(backup_dir=Path("/backups"))
        with patch('searchat.api.routers.backup.get_backup_manager', return_value=manager):
            resp = client.get("/api/backup/chain/backup_20250120_100000")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Backup chain resolution is not available"

    def test_get_backup_chain_fixture_bundle_surfaces_invalid_state(self, client, tmp_path):
        from searchat.services.backup import BackupManager

        fixture = Path("tests/fixtures/storage/backup_contract_bundle")
        shutil.copytree(fixture, tmp_path, dirs_exist_ok=True)
        manager = BackupManager(tmp_path)

        with patch("searchat.api.routers.backup.get_backup_manager", return_value=manager):
            broken = client.get("/api/backup/chain/broken_chain_child")
            invalid = client.get("/api/backup/chain/invalid_manifest_full")

        assert broken.status_code == 200
        broken_payload = broken.json()
        assert broken_payload["chain"] == ["broken_chain_base", "broken_chain_child"]
        assert broken_payload["valid"] is False
        assert any("Backup manifest missing" in error for error in broken_payload["errors"])

        assert invalid.status_code == 200
        invalid_payload = invalid.json()
        assert invalid_payload["chain"] == []
        assert invalid_payload["chain_length"] == 0
        assert invalid_payload["valid"] is False
        assert any("manifest version mismatch" in error.lower() for error in invalid_payload["errors"])

    def test_list_backups_empty(self, client, mock_backup_manager):
        """Test listing when no backups exist."""
        mock_backup_manager.list_backups.return_value = []

        with patch('searchat.api.routers.backup.get_backup_manager', return_value=mock_backup_manager):
            response = client.get("/api/backup/list")

            assert response.status_code == 200
            data = response.json()

            assert data["total"] == 0
            assert len(data["backups"]) == 0

    def test_list_backups_error(self, client, mock_backup_manager):
        """Test error handling when listing fails."""
        mock_backup_manager.list_backups.side_effect = Exception("Permission denied")

        with patch('searchat.api.routers.backup.get_backup_manager', return_value=mock_backup_manager):
            response = client.get("/api/backup/list")

            assert response.status_code == 500
            assert response.json()["detail"] == "Internal server error"


@pytest.mark.unit
class TestRestoreBackupEndpoint:
    """Tests for POST /api/backup/restore endpoint."""

    def test_restore_backup_success(self, client, mock_backup_manager, tmp_path):
        """Test restoring from a backup."""
        # Create backup directory
        backup_dir = tmp_path / "backup_20250120_100000"
        backup_dir.mkdir()

        mock_backup_manager.backup_dir = tmp_path
        mock_backup_manager.restore_from_backup.return_value = None

        with patch('searchat.api.routers.backup.get_backup_manager', return_value=mock_backup_manager):
            with patch('searchat.api.routers.backup.invalidate_search_index') as invalidate:
                response = client.post("/api/backup/restore?backup_name=backup_20250120_100000")

            assert response.status_code == 200
            data = response.json()

            assert list(data) == ["success", "restored_from", "message"]
            assert data["success"] is True
            assert data["restored_from"] == "backup_20250120_100000"
            assert "Successfully restored" in data["message"]

            mock_backup_manager.restore_from_backup.assert_called_once()
            invalidate.assert_called_once()

    def test_restore_backup_not_found(self, client, mock_backup_manager, tmp_path):
        """Test error when backup doesn't exist."""
        mock_backup_manager.backup_dir = tmp_path

        with patch('searchat.api.routers.backup.get_backup_manager', return_value=mock_backup_manager):
            response = client.post("/api/backup/restore?backup_name=nonexistent")

            assert response.status_code == 404
            assert response.json()["detail"] == "Backup not found: nonexistent"

    def test_restore_backup_with_pre_restore_backup(self, client, mock_backup_manager, tmp_path):
        """Test restore creates pre-restore backup."""
        backup_dir = tmp_path / "backup_20250120_100000"
        backup_dir.mkdir()

        mock_backup_manager.backup_dir = tmp_path

        # Mock pre-restore backup metadata
        pre_restore_meta = Mock()
        pre_restore_meta.to_dict.return_value = {"backup_path": "/backups/pre_restore"}
        mock_backup_manager.restore_from_backup.return_value = pre_restore_meta

        with patch('searchat.api.routers.backup.get_backup_manager', return_value=mock_backup_manager):
            with patch('searchat.api.routers.backup.invalidate_search_index'):
                response = client.post("/api/backup/restore?backup_name=backup_20250120_100000")

                assert response.status_code == 200
                data = response.json()

                assert list(data) == ["success", "restored_from", "message", "pre_restore_backup"]
                assert "pre_restore_backup" in data
                assert data["pre_restore_backup"]["backup_path"] == "/backups/pre_restore"


@pytest.mark.unit
class TestDeleteBackupEndpoint:
    """Tests for DELETE /api/backup/delete/{backup_name} endpoint."""

    def test_delete_backup_success(self, client, mock_backup_manager, tmp_path):
        """Test deleting a backup."""
        backup_dir = tmp_path / "backup_20250120_100000"
        backup_dir.mkdir()

        mock_backup_manager.backup_dir = tmp_path

        with patch('searchat.api.routers.backup.get_backup_manager', return_value=mock_backup_manager):
            response = client.delete("/api/backup/delete/backup_20250120_100000")

            assert response.status_code == 200
            data = response.json()

            assert list(data) == ["success", "deleted", "message"]
            assert data["success"] is True
            assert data["deleted"] == "backup_20250120_100000"
            assert "Backup deleted" in data["message"]

            mock_backup_manager.delete_backup.assert_called_once_with(backup_dir)

    def test_delete_backup_not_found(self, client, mock_backup_manager, tmp_path):
        """Test error when backup doesn't exist."""
        mock_backup_manager.backup_dir = tmp_path

        with patch('searchat.api.routers.backup.get_backup_manager', return_value=mock_backup_manager):
            response = client.delete("/api/backup/delete/nonexistent")

            assert response.status_code == 404
            assert response.json()["detail"] == "Backup not found: nonexistent"

    def test_delete_backup_error(self, client, mock_backup_manager, tmp_path):
        """Test error handling when deletion fails."""
        backup_dir = tmp_path / "backup_20250120_100000"
        backup_dir.mkdir()

        mock_backup_manager.backup_dir = tmp_path
        mock_backup_manager.delete_backup.side_effect = Exception("Permission denied")

        with patch('searchat.api.routers.backup.get_backup_manager', return_value=mock_backup_manager):
            response = client.delete("/api/backup/delete/backup_20250120_100000")

            assert response.status_code == 500
            assert response.json()["detail"] == "Internal server error"
