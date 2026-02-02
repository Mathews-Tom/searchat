from __future__ import annotations

import asyncio
import inspect
from typing import Any

import searchat.mcp.tools as tools


def _require_mcp() -> Any:
    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("MCP support is not installed. Install with: pip install 'searchat[mcp]'") from exc
    return FastMCP


def run() -> None:
    """Run the MCP server over stdio."""
    FastMCP = _require_mcp()
    mcp = FastMCP(name="Searchat")

    mcp.tool(name="search_conversations", description="Search conversation history")(tools.search_conversations)
    mcp.tool(name="get_conversation", description="Fetch a conversation by id")(tools.get_conversation)
    mcp.tool(name="find_similar_conversations", description="Find conversations similar to a given one")(
        tools.find_similar_conversations
    )
    mcp.tool(name="ask_about_history", description="Ask a question about your history using RAG")(tools.ask_about_history)
    mcp.tool(name="list_projects", description="List all project ids")(tools.list_projects)
    mcp.tool(name="get_statistics", description="Get index statistics")(tools.get_statistics)

    result = mcp.run()
    if inspect.isawaitable(result):
        async def _main() -> None:
            await result

        asyncio.run(_main())
