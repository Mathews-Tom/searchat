"""AgentProvider protocol — abstraction seam for agent connector operations."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from searchat.config import Config
from searchat.models import ConversationRecord


class AgentProvider(Protocol):
    """Structural contract for agent connectors.

    V1 methods map to the current AgentConnector protocol.
    V2 methods (load_messages, extract_cwd, build_resume_command) are
    implemented by AgentProviderBase ABC in core/connectors/base.py.
    """

    name: str
    supported_extensions: tuple[str, ...]

    # -- V1: current AgentConnector methods --

    def discover_files(self, config: Config) -> list[Path]: ...

    def can_parse(self, path: Path) -> bool: ...

    def parse(self, path: Path, embedding_id: int) -> ConversationRecord: ...
