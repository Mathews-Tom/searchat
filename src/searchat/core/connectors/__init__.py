from .protocols import AgentConnector, ConnectorMatch
from .registry import (
    register_connector,
    get_connectors,
    detect_connector,
    discover_all_files,
    supported_extensions,
    discover_watch_dirs,
    discover_entrypoint_connectors,
)
from .codex import CodexConnector
from .claude import ClaudeConnector
from .vibe import VibeConnector
from .opencode import OpenCodeConnector
from .gemini import GeminiCLIConnector
from .continue_cli import ContinueConnector
from .cursor import CursorConnector
from .aider import AiderConnector

register_connector(CodexConnector())
register_connector(ClaudeConnector())
register_connector(VibeConnector())
register_connector(OpenCodeConnector())
register_connector(GeminiCLIConnector())
register_connector(ContinueConnector())
register_connector(CursorConnector())
register_connector(AiderConnector())

# Optionally load third-party connectors via entry points.
discover_entrypoint_connectors()

__all__ = [
    "AgentConnector",
    "ConnectorMatch",
    "register_connector",
    "discover_entrypoint_connectors",
    "get_connectors",
    "detect_connector",
    "discover_all_files",
    "supported_extensions",
    "discover_watch_dirs",
]
