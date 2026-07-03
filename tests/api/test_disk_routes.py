"""Unit tests for the disk accounting API route."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from searchat.api.app import app
from searchat.services.disk_accounting import (
    AgentDiskUsage,
    CruftFinding,
    DiskAccountingReport,
    SearchatSelfUsage,
    SubdirectoryUsage,
)


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_agent_usage():
    """`AgentDiskUsage` for one registered connector."""
    return AgentDiskUsage(
        connector="claude-code",
        watch_dirs=("/home/user/.claude/projects",),
        total_size_bytes=104857600,
        total_file_count=42,
        conversation_file_count=40,
        indexed_file_count=35,
        indexed_size_bytes=90000000,
        unindexed_file_count=5,
        unindexed_size_bytes=14857600,
        oldest_conversation_age_days=120.5,
        newest_conversation_age_days=0.5,
        age_histogram={"0-7d": 3, "7-30d": 10, "30-90d": 15, "90-365d": 12, "365d+": 0},
    )


@pytest.fixture
def mock_subdirectories():
    """`SubdirectoryUsage` entries for Searchat's own self-accounting."""
    return (
        SubdirectoryUsage(
            label="index",
            path="/home/user/.searchat/data",
            exists=True,
            total_size_bytes=52428800,
            file_count=8,
        ),
        SubdirectoryUsage(
            label="backups",
            path="/home/user/.searchat/backups",
            exists=False,
            total_size_bytes=0,
            file_count=0,
        ),
    )


@pytest.fixture
def mock_report(mock_agent_usage, mock_subdirectories):
    """Full `DiskAccountingReport` with one agent and Searchat self usage."""
    return DiskAccountingReport(
        agents=(mock_agent_usage,),
        searchat_self=SearchatSelfUsage(
            search_dir="/home/user/.searchat",
            subdirectories=mock_subdirectories,
            total_size_bytes=52428800,
            total_file_count=8,
        ),
        generated_at="2026-07-03T12:00:00",
    )


@pytest.fixture
def mock_empty_report(mock_subdirectories):
    """`DiskAccountingReport` with no registered connectors."""
    return DiskAccountingReport(
        agents=(),
        searchat_self=SearchatSelfUsage(
            search_dir="/home/user/.searchat",
            subdirectories=mock_subdirectories,
            total_size_bytes=52428800,
            total_file_count=8,
        ),
        generated_at="2026-07-03T12:00:00",
    )


@pytest.mark.unit
class TestDiskAccountingEndpoint:
    """Tests for GET /api/disk endpoint."""

    def test_get_disk_accounting_success(self, client, mock_report):
        """Full report round-trips through the response schema with correct values."""
        with patch('searchat.api.routers.disk.get_search_dir', return_value=Path("/home/user/.searchat")):
            with patch('searchat.api.routers.disk.get_config', return_value=Mock()):
                with patch(
                    'searchat.api.routers.disk.build_disk_accounting_report',
                    return_value=mock_report,
                ) as mock_build:
                    response = client.get("/api/disk")

        assert response.status_code == 200
        data = response.json()

        assert list(data) == [
            "agents",
            "searchat_self",
            "generated_at",
            "cruft_findings",
        ]
        assert data["generated_at"] == "2026-07-03T12:00:00"

        assert len(data["agents"]) == 1
        agent = data["agents"][0]
        assert agent["connector"] == "claude-code"
        assert agent["watch_dirs"] == ["/home/user/.claude/projects"]
        assert agent["total_size_bytes"] == 104857600
        assert agent["total_file_count"] == 42
        assert agent["conversation_file_count"] == 40
        assert agent["indexed_file_count"] == 35
        assert agent["indexed_size_bytes"] == 90000000
        assert agent["unindexed_file_count"] == 5
        assert agent["unindexed_size_bytes"] == 14857600
        assert agent["oldest_conversation_age_days"] == 120.5
        assert agent["newest_conversation_age_days"] == 0.5
        assert agent["age_histogram"] == {
            "0-7d": 3,
            "7-30d": 10,
            "30-90d": 15,
            "90-365d": 12,
            "365d+": 0,
        }

        self_usage = data["searchat_self"]
        assert self_usage["search_dir"] == "/home/user/.searchat"
        assert self_usage["total_size_bytes"] == 52428800
        assert self_usage["total_file_count"] == 8
        assert len(self_usage["subdirectories"]) == 2
        assert self_usage["subdirectories"][0] == {
            "label": "index",
            "path": "/home/user/.searchat/data",
            "exists": True,
            "total_size_bytes": 52428800,
            "file_count": 8,
        }
        assert self_usage["subdirectories"][1]["exists"] is False

        mock_build.assert_called_once()

    def test_get_disk_accounting_empty_agents(self, client, mock_empty_report):
        """No registered connectors still returns 200 with an empty agents list."""
        with patch('searchat.api.routers.disk.get_search_dir', return_value=Path("/home/user/.searchat")):
            with patch('searchat.api.routers.disk.get_config', return_value=Mock()):
                with patch(
                    'searchat.api.routers.disk.build_disk_accounting_report',
                    return_value=mock_empty_report,
                ):
                    response = client.get("/api/disk")

        assert response.status_code == 200
        data = response.json()
        assert data["agents"] == []
        assert len(data["searchat_self"]["subdirectories"]) == 2

    def test_get_disk_accounting_error(self, client):
        """Any exception from the service layer surfaces as a generic 500."""
        with patch('searchat.api.routers.disk.get_search_dir', return_value=Path("/home/user/.searchat")):
            with patch('searchat.api.routers.disk.get_config', return_value=Mock()):
                with patch(
                    'searchat.api.routers.disk.build_disk_accounting_report',
                    side_effect=Exception("DuckDB connection failed"),
                ):
                    response = client.get("/api/disk")

        assert response.status_code == 500
        assert response.json()["detail"] == "Internal server error"

    def test_get_disk_accounting_response_schema(self, client, mock_report):
        """Every declared field is present with the expected JSON type."""
        with patch('searchat.api.routers.disk.get_search_dir', return_value=Path("/home/user/.searchat")):
            with patch('searchat.api.routers.disk.get_config', return_value=Mock()):
                with patch(
                    'searchat.api.routers.disk.build_disk_accounting_report',
                    return_value=mock_report,
                ):
                    response = client.get("/api/disk")

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data["agents"], list)
        assert isinstance(data["searchat_self"], dict)
        assert isinstance(data["generated_at"], str)

        agent = data["agents"][0]
        assert isinstance(agent["connector"], str)
        assert isinstance(agent["watch_dirs"], list)
        assert all(isinstance(d, str) for d in agent["watch_dirs"])
        assert isinstance(agent["total_size_bytes"], int)
        assert isinstance(agent["total_file_count"], int)
        assert isinstance(agent["conversation_file_count"], int)
        assert isinstance(agent["indexed_file_count"], int)
        assert isinstance(agent["indexed_size_bytes"], int)
        assert isinstance(agent["unindexed_file_count"], int)
        assert isinstance(agent["unindexed_size_bytes"], int)
        assert isinstance(agent["oldest_conversation_age_days"], float)
        assert isinstance(agent["newest_conversation_age_days"], float)
        assert isinstance(agent["age_histogram"], dict)
        assert all(isinstance(v, int) for v in agent["age_histogram"].values())

        self_usage = data["searchat_self"]
        assert isinstance(self_usage["search_dir"], str)
        assert isinstance(self_usage["subdirectories"], list)
        assert isinstance(self_usage["total_size_bytes"], int)
        assert isinstance(self_usage["total_file_count"], int)

        subdir = self_usage["subdirectories"][0]
        assert isinstance(subdir["label"], str)
        assert isinstance(subdir["path"], str)
        assert isinstance(subdir["exists"], bool)
        assert isinstance(subdir["total_size_bytes"], int)
        assert isinstance(subdir["file_count"], int)

    def test_get_disk_accounting_includes_cruft_findings(
        self, client, mock_agent_usage, mock_subdirectories
    ):
        """Cruft findings round-trip through `CruftFindingResponse` with all seven
        fields intact -- proves the response model doesn't silently drop/rename
        anything.
        """
        cruft_findings = (
            CruftFinding(
                label="Codex CLI log database",
                path="/home/user/.codex/logs_2.sqlite",
                path_glob=".codex/logs_2.sqlite",
                explanation="OpenAI Codex CLI's internal SQLite log store.",
                cleanup_hint=None,
                total_size_bytes=4096,
                file_count=1,
            ),
            CruftFinding(
                label="Claude Code plugins",
                path="/home/user/.claude/plugins",
                path_glob=".claude/plugins",
                explanation="Installed Claude Code plugin and MCP-server data.",
                cleanup_hint="claude plugins clean",
                total_size_bytes=2048,
                file_count=3,
            ),
        )
        report = DiskAccountingReport(
            agents=(mock_agent_usage,),
            searchat_self=SearchatSelfUsage(
                search_dir="/home/user/.searchat",
                subdirectories=mock_subdirectories,
                total_size_bytes=52428800,
                total_file_count=8,
            ),
            generated_at="2026-07-03T12:00:00",
            cruft_findings=cruft_findings,
        )

        with patch(
            "searchat.api.routers.disk.get_search_dir",
            return_value=Path("/home/user/.searchat"),
        ):
            with patch("searchat.api.routers.disk.get_config", return_value=Mock()):
                with patch(
                    "searchat.api.routers.disk.build_disk_accounting_report",
                    return_value=report,
                ):
                    response = client.get("/api/disk")

        assert response.status_code == 200
        data = response.json()

        assert len(data["cruft_findings"]) == 2
        for expected, actual in zip(cruft_findings, data["cruft_findings"]):
            assert actual == {
                "label": expected.label,
                "path": expected.path,
                "path_glob": expected.path_glob,
                "explanation": expected.explanation,
                "cleanup_hint": expected.cleanup_hint,
                "total_size_bytes": expected.total_size_bytes,
                "file_count": expected.file_count,
            }

    def test_get_disk_accounting_null_ages_when_no_conversations(self, client, mock_subdirectories):
        """Optional age fields serialize as JSON null when no conversation files exist."""
        agent = AgentDiskUsage(
            connector="empty-connector",
            watch_dirs=(),
            total_size_bytes=0,
            total_file_count=0,
            conversation_file_count=0,
            indexed_file_count=0,
            indexed_size_bytes=0,
            unindexed_file_count=0,
            unindexed_size_bytes=0,
            oldest_conversation_age_days=None,
            newest_conversation_age_days=None,
            age_histogram={"0-7d": 0, "7-30d": 0, "30-90d": 0, "90-365d": 0, "365d+": 0},
        )
        report = DiskAccountingReport(
            agents=(agent,),
            searchat_self=SearchatSelfUsage(
                search_dir="/home/user/.searchat",
                subdirectories=mock_subdirectories,
                total_size_bytes=52428800,
                total_file_count=8,
            ),
            generated_at="2026-07-03T12:00:00",
        )

        with patch('searchat.api.routers.disk.get_search_dir', return_value=Path("/home/user/.searchat")):
            with patch('searchat.api.routers.disk.get_config', return_value=Mock()):
                with patch(
                    'searchat.api.routers.disk.build_disk_accounting_report',
                    return_value=report,
                ):
                    response = client.get("/api/disk")

        assert response.status_code == 200
        data = response.json()
        assert data["agents"][0]["oldest_conversation_age_days"] is None
        assert data["agents"][0]["newest_conversation_age_days"] is None

    def test_get_disk_accounting_calls_service_with_search_dir_and_config(self, client, mock_report):
        """The route wires `get_search_dir()`/`get_config()`/the live DuckDB connection into the service call."""
        fake_search_dir = Path("/home/user/.searchat")
        fake_config = Mock(name="fake_config")
        fake_connection = Mock(name="fake_duckdb_connection")
        fake_store = Mock(name="fake_duckdb_store")
        fake_store.connection = fake_connection

        with patch(
            'searchat.api.routers.disk.get_search_dir', return_value=fake_search_dir
        ) as mock_get_dir:
            with patch(
                'searchat.api.routers.disk.get_config', return_value=fake_config
            ) as mock_get_config:
                with patch(
                    'searchat.api.routers.disk.get_duckdb_store', return_value=fake_store
                ) as mock_get_store:
                    with patch(
                        'searchat.api.routers.disk.build_disk_accounting_report',
                        return_value=mock_report,
                    ) as mock_build:
                        response = client.get("/api/disk")

        assert response.status_code == 200
        mock_get_dir.assert_called_once()
        mock_get_config.assert_called_once()
        mock_get_store.assert_called_once()
        mock_build.assert_called_once_with(fake_search_dir, fake_config, connection=fake_connection)

    def test_get_disk_accounting_falls_back_when_duckdb_store_unavailable(self, client, mock_report):
        """If `get_duckdb_store()` raises (services not initialized), the route degrades to a
        fresh-connection call instead of failing the whole request with a 500.
        """
        fake_search_dir = Path("/home/user/.searchat")
        fake_config = Mock(name="fake_config")

        with patch('searchat.api.routers.disk.get_search_dir', return_value=fake_search_dir):
            with patch('searchat.api.routers.disk.get_config', return_value=fake_config):
                with patch(
                    'searchat.api.routers.disk.get_duckdb_store',
                    side_effect=RuntimeError("Services not initialized"),
                ):
                    with patch(
                        'searchat.api.routers.disk.build_disk_accounting_report',
                        return_value=mock_report,
                    ) as mock_build:
                        response = client.get("/api/disk")

        assert response.status_code == 200
        mock_build.assert_called_once_with(fake_search_dir, fake_config, connection=None)

    def test_get_disk_accounting_offloads_via_asyncio_to_thread(self, client, mock_report):
        """The heavy filesystem walk runs via `asyncio.to_thread`, not a direct synchronous call.

        Mocking `asyncio.to_thread` itself -- rather than `build_disk_accounting_report` -- is
        the only way to distinguish `await asyncio.to_thread(fn, ...)` from `fn(...)`: only the
        former ever reaches this mock. Asserting the mock's call signature plus that the real
        service function was never invoked directly proves the route genuinely offloads the scan
        instead of running it inline on the event loop.
        """
        fake_search_dir = Path("/home/user/.searchat")
        fake_config = Mock(name="fake_config")

        with patch('searchat.api.routers.disk.get_search_dir', return_value=fake_search_dir):
            with patch('searchat.api.routers.disk.get_config', return_value=fake_config):
                with patch(
                    'searchat.api.routers.disk.build_disk_accounting_report'
                ) as mock_build:
                    with patch(
                        'searchat.api.routers.disk.asyncio.to_thread',
                        new_callable=AsyncMock,
                        return_value=mock_report,
                    ) as mock_to_thread:
                        response = client.get("/api/disk")

        assert response.status_code == 200
        mock_to_thread.assert_called_once_with(
            mock_build, fake_search_dir, fake_config, connection=None
        )
        mock_build.assert_not_called()
