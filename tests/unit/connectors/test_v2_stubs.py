"""Tests for stub connector V2 methods (default no-ops)."""
from __future__ import annotations

from pathlib import Path

import pytest

from searchat.core.connectors.gemini import GeminiCLIConnector
from searchat.core.connectors.continue_cli import ContinueConnector
from searchat.core.connectors.cursor import CursorConnector
from searchat.core.connectors.aider import AiderConnector


STUB_CONNECTORS = [
    GeminiCLIConnector,
    ContinueConnector,
    CursorConnector,
    AiderConnector,
]


@pytest.fixture(params=STUB_CONNECTORS, ids=lambda cls: cls.__name__)
def stub_connector(request: pytest.FixtureRequest):
    return request.param()


class TestStubV2Methods:
    def test_load_messages_returns_empty_list(self, stub_connector, tmp_path) -> None:
        path = tmp_path / "fake.json"
        path.write_text("{}", encoding="utf-8")
        assert stub_connector.load_messages(path) == []

    def test_extract_cwd_returns_none(self, stub_connector, tmp_path) -> None:
        path = tmp_path / "fake.json"
        path.write_text("{}", encoding="utf-8")
        assert stub_connector.extract_cwd(path) is None

    def test_build_resume_command_returns_none(self, stub_connector, tmp_path) -> None:
        path = tmp_path / "fake.json"
        path.write_text("{}", encoding="utf-8")
        assert stub_connector.build_resume_command(path) is None
