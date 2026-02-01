from __future__ import annotations

from pathlib import Path
from collections.abc import Mapping

from searchat.config import Config
from searchat.core.logging_config import get_logger

from .protocols import AgentConnector, ConnectorMatch


logger = get_logger(__name__)


_CONNECTORS: list[AgentConnector] = []


def discover_entrypoint_connectors() -> int:
    """Load connectors from `searchat.connectors` entry points.

    Returns:
        Number of newly registered connectors.
    """
    try:
        from importlib.metadata import entry_points
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("importlib.metadata is required") from exc

    registered = {c.name for c in _CONNECTORS}
    loaded = 0

    try:
        eps = entry_points()
        if hasattr(eps, "select"):
            group_eps = list(eps.select(group="searchat.connectors"))
        elif isinstance(eps, Mapping):
            group_eps = list(eps.get("searchat.connectors", []))
        else:
            group_eps = []
    except Exception as exc:
        logger.warning("Failed to enumerate connector entry points: %s", exc)
        return 0

    for ep in group_eps:
        try:
            obj = ep.load()
        except Exception as exc:
            logger.warning("Failed to load connector entry point %s: %s", getattr(ep, "name", "<unknown>"), exc)
            continue

        try:
            connector = obj() if isinstance(obj, type) else obj
        except Exception as exc:
            logger.warning("Failed to instantiate connector %s: %s", getattr(ep, "name", "<unknown>"), exc)
            continue

        name = getattr(connector, "name", None)
        if not isinstance(name, str) or not name:
            logger.warning("Skipping connector %s: missing valid name", getattr(ep, "name", "<unknown>"))
            continue
        if name in registered:
            continue

        try:
            register_connector(connector)
        except Exception as exc:
            logger.warning("Failed to register connector %s: %s", name, exc)
            continue

        registered.add(name)
        loaded += 1

    return loaded


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
