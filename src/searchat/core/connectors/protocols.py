from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from searchat.config import Config
from searchat.models import ConversationRecord


@runtime_checkable
class AgentConnector(Protocol):
    """V1 structural contract for agent connectors.

    V2 methods (load_messages, extract_cwd, build_resume_command) live on
    AgentProviderBase and are accessed via isinstance/hasattr checks, not
    through this protocol — keeping registration backward-compatible.
    """

    name: str
    supported_extensions: tuple[str, ...]

    def discover_files(self, config: Config) -> list[Path]:
        ...

    def can_parse(self, path: Path) -> bool:
        ...

    def parse(self, path: Path, embedding_id: int) -> ConversationRecord:
        ...


@dataclass(frozen=True)
class ConnectorMatch:
    connector: AgentConnector
    path: Path
