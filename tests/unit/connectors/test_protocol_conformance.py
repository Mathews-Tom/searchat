"""Protocol conformance tests for all 8 agent connectors.

Verifies that each connector:
1. Is an instance of AgentProviderBase (ABC)
2. Satisfies the AgentConnector protocol (V1)
3. Has V2 methods (load_messages, extract_cwd, build_resume_command)
4. Has correct name and supported_extensions attributes
"""
from __future__ import annotations

import pytest

from searchat.core.connectors.base import AgentProviderBase
from searchat.core.connectors.protocols import AgentConnector
from searchat.core.connectors.registry import has_v2_support
from searchat.core.connectors.claude import ClaudeConnector
from searchat.core.connectors.vibe import VibeConnector
from searchat.core.connectors.codex import CodexConnector
from searchat.core.connectors.opencode import OpenCodeConnector
from searchat.core.connectors.gemini import GeminiCLIConnector
from searchat.core.connectors.continue_cli import ContinueConnector
from searchat.core.connectors.cursor import CursorConnector
from searchat.core.connectors.aider import AiderConnector


ALL_CONNECTOR_CLASSES = [
    ClaudeConnector,
    VibeConnector,
    CodexConnector,
    OpenCodeConnector,
    GeminiCLIConnector,
    ContinueConnector,
    CursorConnector,
    AiderConnector,
]

EXPECTED_NAMES = {
    ClaudeConnector: "claude",
    VibeConnector: "vibe",
    CodexConnector: "codex",
    OpenCodeConnector: "opencode",
    GeminiCLIConnector: "gemini",
    ContinueConnector: "continue",
    CursorConnector: "cursor",
    AiderConnector: "aider",
}


@pytest.fixture(params=ALL_CONNECTOR_CLASSES, ids=lambda cls: cls.__name__)
def connector(request: pytest.FixtureRequest) -> AgentProviderBase:
    return request.param()


class TestProtocolConformance:
    def test_is_agent_provider_base(self, connector: AgentProviderBase) -> None:
        assert isinstance(connector, AgentProviderBase)

    def test_satisfies_agent_connector_protocol(self, connector: AgentProviderBase) -> None:
        assert isinstance(connector, AgentConnector)

    def test_has_v2_support(self, connector: AgentProviderBase) -> None:
        assert has_v2_support(connector)

    def test_has_name_attribute(self, connector: AgentProviderBase) -> None:
        assert isinstance(connector.name, str)
        assert len(connector.name) > 0

    def test_has_correct_name(self, connector: AgentProviderBase) -> None:
        expected = EXPECTED_NAMES.get(type(connector))
        if expected is not None:
            assert connector.name == expected

    def test_has_supported_extensions(self, connector: AgentProviderBase) -> None:
        assert isinstance(connector.supported_extensions, tuple)
        assert len(connector.supported_extensions) > 0
        for ext in connector.supported_extensions:
            assert isinstance(ext, str)
            assert ext.startswith(".")

    def test_has_v1_methods(self, connector: AgentProviderBase) -> None:
        assert callable(getattr(connector, "discover_files", None))
        assert callable(getattr(connector, "can_parse", None))
        assert callable(getattr(connector, "parse", None))

    def test_has_v2_methods(self, connector: AgentProviderBase) -> None:
        assert callable(getattr(connector, "load_messages", None))
        assert callable(getattr(connector, "extract_cwd", None))
        assert callable(getattr(connector, "build_resume_command", None))
