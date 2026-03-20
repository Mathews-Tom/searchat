from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest


def test_health_cmd_success(capsys: pytest.CaptureFixture[str]) -> None:
    from searchat.cli.health_cmd import run_health

    response_body = json.dumps({
        "healthy": True,
        "checks": {
            "duckdb": {"status": "ok", "latency_ms": 1.2, "conversations": 42},
        },
    }).encode()

    resp = MagicMock()
    resp.read.return_value = response_body
    resp.status = 200
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=resp):
        exit_code = run_health(["--json"])

    assert exit_code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["healthy"] is True


def test_health_cmd_unhealthy_exit_code(capsys: pytest.CaptureFixture[str]) -> None:
    from searchat.cli.health_cmd import run_health

    response_body = json.dumps({
        "healthy": False,
        "checks": {
            "duckdb": {"status": "error", "latency_ms": 0.5, "error": "corrupt"},
        },
    }).encode()

    resp = MagicMock()
    resp.read.return_value = response_body
    resp.status = 503
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=resp):
        exit_code = run_health(["--json"])

    assert exit_code == 1


def test_health_cmd_unreachable_server(capsys: pytest.CaptureFixture[str]) -> None:
    from searchat.cli.health_cmd import run_health
    import urllib.error

    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
        exit_code = run_health(["--url", "http://localhost:9999"])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "cannot reach server" in captured.err


def test_health_cmd_help(capsys: pytest.CaptureFixture[str]) -> None:
    from searchat.cli.health_cmd import run_health

    exit_code = run_health(["--help"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "--url" in captured.out
    assert "--json" in captured.out


def test_health_cmd_http_error_parses_body(capsys: pytest.CaptureFixture[str]) -> None:
    from searchat.cli.health_cmd import run_health
    import urllib.error

    response_body = json.dumps({
        "healthy": False,
        "checks": {"duckdb": {"status": "error", "latency_ms": 0.1}},
    }).encode()

    exc = urllib.error.HTTPError(
        url="http://localhost:8000/api/health",
        code=503,
        msg="Service Unavailable",
        hdrs=None,  # type: ignore[arg-type]
        fp=None,
    )
    exc.read = MagicMock(return_value=response_body)  # type: ignore[method-assign]

    with patch("urllib.request.urlopen", side_effect=exc):
        exit_code = run_health(["--json"])

    assert exit_code == 1
    data = json.loads(capsys.readouterr().out)
    assert data["healthy"] is False
