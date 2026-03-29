"""AgentProviderBase — abstract base combining V1 connector + V2 provider methods."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from searchat.config import Config
from searchat.models import ConversationRecord


class AgentProviderBase(ABC):
    """ABC that unifies AgentConnector (V1) with AgentProvider (V2) capabilities.

    V1 methods (discover_files, can_parse, parse) are abstract — every connector
    must implement them.

    V2 methods (load_messages, extract_cwd, build_resume_command) have default
    no-op implementations so existing connectors remain backward-compatible.
    Connectors with real data for these operations override them.
    """

    name: str
    supported_extensions: tuple[str, ...]

    # -- V1: existing AgentConnector interface (abstract) --

    @abstractmethod
    def discover_files(self, config: Config) -> list[Path]:
        """Discover conversation files for this agent."""
        ...

    @abstractmethod
    def can_parse(self, path: Path) -> bool:
        """Return True if this connector can parse the given file."""
        ...

    @abstractmethod
    def parse(self, path: Path, embedding_id: int) -> ConversationRecord:
        """Parse a conversation file into a ConversationRecord."""
        ...

    # -- V2: AgentProvider methods (default no-ops) --

    def load_messages(self, path: Path) -> list[dict[str, Any]]:
        """Load raw messages from a conversation file for replay/resumption.

        Returns a list of message dicts with at minimum 'role' and 'content' keys.
        Default: empty list (connector does not support message loading).
        """
        return []

    def extract_cwd(self, path: Path) -> str | None:
        """Extract the working directory from a conversation file.

        Returns the absolute path string of the working directory,
        or None if not available.
        Default: None (connector cannot extract working directory).
        """
        return None

    def build_resume_command(self, path: Path) -> str | None:
        """Build a shell command to resume/continue the conversation.

        Returns a command string that can be executed to resume the session,
        or None if resumption is not supported.
        Default: None (connector does not support resumption).
        """
        return None
