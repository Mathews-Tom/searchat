"""Regression tests for the cross-origin state-changing request rejection.

CORSMiddleware alone does not stop a "simple" cross-origin POST (a bare
`<form method=POST>`, no custom Content-Type) from being sent and
executed server-side -- it only withholds `Access-Control-Allow-Origin`
from the *response*, which blocks a malicious page's JS from *reading*
the result but does nothing to stop the mutation itself. Before this
fix, any website the user's browser visited could silently auto-submit
a hidden form to a state-changing endpoint like `POST /api/backup/create`
or `POST /api/index_missing` on this locally-bound, unauthenticated
server -- a classic "drive-by localhost" attack.

`RejectCrossOriginMutationsMiddleware` closes this by rejecting any
non-GET/HEAD/OPTIONS request whose browser-sent `Origin` header is
present but not in the configured CORS allowlist. Requests with no
Origin header (curl, Python's `requests`, the MCP stdio transport) are
left untouched, since a non-browser client cannot mount this specific
attack (no ambient browser session to hijack) and blocking them would
break legitimate direct API/CLI usage.
"""
from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from searchat.api.app import app

EVIL_ORIGIN = "https://evil.example.com"
ALLOWED_ORIGIN = "http://localhost:8000"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def mock_backup_manager():
    mock = Mock()
    mock_metadata = Mock()
    mock_metadata.to_dict.return_value = {
        "backup_path": "/backups/backup_20250120_100000",
        "timestamp": "20250120_100000",
        "file_count": 5,
        "total_size_mb": 10.5,
    }
    mock.create_backup.return_value = mock_metadata
    return mock


@pytest.mark.unit
class TestRejectCrossOriginMutations:
    def test_foreign_origin_post_is_rejected_before_reaching_the_endpoint(
        self, client: TestClient, mock_backup_manager
    ) -> None:
        """A drive-by form POST from an attacker's own website carries the
        attacker's Origin. This must never reach create_backup()."""
        with patch(
            "searchat.api.routers.backup.get_backup_manager",
            return_value=mock_backup_manager,
        ):
            response = client.post(
                "/api/backup/create", headers={"Origin": EVIL_ORIGIN}
            )

        assert response.status_code == 403
        mock_backup_manager.create_backup.assert_not_called()

    def test_allowed_origin_post_reaches_the_endpoint(
        self, client: TestClient, mock_backup_manager
    ) -> None:
        with patch(
            "searchat.api.routers.backup.get_backup_manager",
            return_value=mock_backup_manager,
        ):
            response = client.post(
                "/api/backup/create", headers={"Origin": ALLOWED_ORIGIN}
            )

        assert response.status_code == 200
        mock_backup_manager.create_backup.assert_called_once()

    def test_no_origin_header_reaches_the_endpoint(
        self, client: TestClient, mock_backup_manager
    ) -> None:
        """Non-browser clients (curl, Python requests, the MCP stdio
        transport) never set an Origin header and must not be blocked."""
        with patch(
            "searchat.api.routers.backup.get_backup_manager",
            return_value=mock_backup_manager,
        ):
            response = client.post("/api/backup/create")

        assert response.status_code == 200
        mock_backup_manager.create_backup.assert_called_once()

    def test_foreign_origin_get_is_not_blocked(self, client: TestClient) -> None:
        """GET is never state-changing; a foreign Origin must not block it.

        No backup manager is mocked here on purpose: the only thing under
        test is that the middleware does not intercept the request. A 403
        would prove a block; any other status proves the request reached
        the route handler.
        """
        response = client.get("/api/backup/list", headers={"Origin": EVIL_ORIGIN})

        assert response.status_code != 403

    def test_foreign_origin_index_missing_is_rejected(self, client: TestClient) -> None:
        """A second, independent state-changing endpoint carrying no body
        at all -- the whole request is just the Origin header."""
        response = client.post(
            "/api/index_missing", headers={"Origin": EVIL_ORIGIN}
        )

        assert response.status_code == 403

    def test_same_origin_as_host_header_is_allowed_even_when_not_in_static_allowlist(
        self, client: TestClient, mock_backup_manager
    ) -> None:
        """Regression for the static-allowlist bug: main()'s own port
        auto-scanner (PORT_SCAN_RANGE 8000-8010) silently binds to a
        non-default port whenever 8000 is taken, and SEARCHAT_HOST=0.0.0.0
        deployments are reached via a LAN IP -- neither is in the static
        cors_origins default, so the app's own legitimate frontend must
        not be blocked just because its Origin isn't in that list, as
        long as it matches the request's own Host header (TestClient's
        default Host is 'testserver', with no port -- matching an Origin
        of http://testserver that is deliberately NOT in ALLOWED_ORIGIN).
        """
        with patch(
            "searchat.api.routers.backup.get_backup_manager",
            return_value=mock_backup_manager,
        ):
            response = client.post(
                "/api/backup/create", headers={"Origin": "http://testserver"}
            )

        assert response.status_code == 200
        mock_backup_manager.create_backup.assert_called_once()

    def test_mismatched_port_origin_is_still_rejected(
        self, client: TestClient, mock_backup_manager
    ) -> None:
        """An Origin whose host:port does not match Host, and is not in
        the static allowlist, must still be rejected -- same-origin
        matching is not a blanket bypass."""
        with patch(
            "searchat.api.routers.backup.get_backup_manager",
            return_value=mock_backup_manager,
        ):
            response = client.post(
                "/api/backup/create", headers={"Origin": "http://testserver:9999"}
            )

        assert response.status_code == 403
        mock_backup_manager.create_backup.assert_not_called()
