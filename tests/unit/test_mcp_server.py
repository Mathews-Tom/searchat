"""Tests for MCP server entry point."""
from __future__ import annotations

import types
from unittest.mock import MagicMock, patch

import pytest


class TestRequireMcp:
    def test_returns_fastmcp_class_when_available(self):
        from searchat.mcp.server import _require_mcp

        fake_class = type("FastMCP", (), {})
        mod = types.SimpleNamespace(FastMCP=fake_class)
        with patch.dict("sys.modules", {"mcp": MagicMock(), "mcp.server": MagicMock(), "mcp.server.fastmcp": mod}):
            result = _require_mcp()
        assert result is fake_class

    def test_raises_runtime_error_when_mcp_missing(self):
        from searchat.mcp.server import _require_mcp

        with patch.dict("sys.modules", {"mcp": None, "mcp.server": None, "mcp.server.fastmcp": None}):
            with pytest.raises(RuntimeError, match="MCP support is not installed"):
                _require_mcp()


class TestRunMcpServer:
    def test_run_registers_tools_and_calls_run(self):
        from searchat.mcp import server

        fake_mcp = MagicMock()
        fake_mcp.run.return_value = None  # non-awaitable
        fake_mcp.tool.return_value = lambda fn: fn

        fake_fastmcp_cls = MagicMock(return_value=fake_mcp)

        with patch.object(server, "_require_mcp", return_value=fake_fastmcp_cls):
            server.run()

        fake_fastmcp_cls.assert_called_once_with(name="Searchat")
        assert fake_mcp.tool.call_count == 9  # 6 original + 3 expertise
        fake_mcp.run.assert_called_once()

    def test_run_handles_awaitable_result(self):
        """When mcp.run() returns an awaitable, it should be awaited via asyncio.run."""
        from searchat.mcp import server

        fake_mcp = MagicMock()

        async def _fake_coro():
            pass

        coro = _fake_coro()
        fake_mcp.run.return_value = coro
        fake_mcp.tool.return_value = lambda fn: fn

        fake_fastmcp_cls = MagicMock(return_value=fake_mcp)

        with (
            patch.object(server, "_require_mcp", return_value=fake_fastmcp_cls),
            patch("asyncio.run") as mock_asyncio_run,
        ):
            server.run()

        mock_asyncio_run.assert_called_once()

        # Close unawaited coroutines to avoid RuntimeWarning leaking into subsequent tests
        inner_coro = mock_asyncio_run.call_args[0][0]
        inner_coro.close()
        coro.close()
