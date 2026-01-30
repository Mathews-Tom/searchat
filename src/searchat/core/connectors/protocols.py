from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from searchat.config import Config
from searchat.models import ConversationRecord


class AgentConnector(Protocol):
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
