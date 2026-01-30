from __future__ import annotations

from pathlib import Path

from searchat.config import Config
from searchat.core.logging_config import get_logger

from .protocols import AgentConnector, ConnectorMatch


logger = get_logger(__name__)


_CONNECTORS: list[AgentConnector] = []


def register_connector(connector: AgentConnector) -> None:
    required_attrs = ("name", "supported_extensions", "discover_files", "can_parse", "parse")
    for attr in required_attrs:
        if not hasattr(connector, attr):
            raise ValueError(f"Connector missing required attribute: {attr}")
    extensions = connector.supported_extensions
    if not isinstance(extensions, tuple):
        raise ValueError("Connector supported_extensions must be a tuple of strings")
    for ext in extensions:
        if not isinstance(ext, str) or not ext.startswith("."):
            raise ValueError(f"Invalid extension in supported_extensions: {ext}")
    if any(existing.name == connector.name for existing in _CONNECTORS):
        raise ValueError(f"Connector already registered: {connector.name}")
    _CONNECTORS.append(connector)


def get_connectors() -> tuple[AgentConnector, ...]:
    return tuple(_CONNECTORS)


def discover_all_files(config: Config) -> list[ConnectorMatch]:
    matches: list[ConnectorMatch] = []
    for connector in _CONNECTORS:
        for path in connector.discover_files(config):
            matches.append(ConnectorMatch(connector=connector, path=path))
    return matches


def detect_connector(path: Path) -> AgentConnector:
    for connector in _CONNECTORS:
        if connector.can_parse(path):
            return connector
    raise ValueError(f"No connector found for {path}")


def supported_extensions() -> tuple[str, ...]:
    extensions: list[str] = []
    for connector in _CONNECTORS:
        extensions.extend(connector.supported_extensions)
    return tuple(sorted(set(extensions)))


def discover_watch_dirs(config: Config) -> list[Path]:
    dirs: list[Path] = []
    for connector in _CONNECTORS:
        watch_dirs = getattr(connector, "watch_dirs", None)
        if callable(watch_dirs):
            for watch_dir in watch_dirs(config):
                dirs.append(watch_dir)
            continue
        for match in connector.discover_files(config):
            dirs.append(match.parent)
    seen: set[str] = set()
    unique: list[Path] = []
    for path in dirs:
        path_str = str(path.resolve()) if path.exists() else str(path)
        if path_str in seen:
            continue
        seen.add(path_str)
        unique.append(path)
    return unique
