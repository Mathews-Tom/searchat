from .protocols import AgentConnector, ConnectorMatch
from .registry import (
    register_connector,
    get_connectors,
    detect_connector,
    discover_all_files,
    supported_extensions,
    discover_watch_dirs,
)
from .claude import ClaudeConnector
from .vibe import VibeConnector
from .opencode import OpenCodeConnector

register_connector(ClaudeConnector())
register_connector(VibeConnector())
register_connector(OpenCodeConnector())

__all__ = [
    "AgentConnector",
    "ConnectorMatch",
    "register_connector",
    "get_connectors",
    "detect_connector",
    "discover_all_files",
    "supported_extensions",
    "discover_watch_dirs",
]
