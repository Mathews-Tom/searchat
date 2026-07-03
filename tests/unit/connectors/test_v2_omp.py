"""Unit tests for OmpConnector V1 (discover/parse) and V2 methods."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from searchat.core.connectors.omp import OmpConnector

FIXTURES_ROOT = Path("tests/fixtures/connectors/omp/sessions/-tmp-demo-project")
SESSION_1 = FIXTURES_ROOT / "2026-03-29T10-00-00-000Z_01900000-0000-7000-8000-000000000001.jsonl"
SESSION_2 = FIXTURES_ROOT / "2026-03-29T11-00-00-000Z_01900000-0000-7000-8000-000000000002.jsonl"
NESTED_SUBAGENT = (
    FIXTURES_ROOT
    / "2026-03-29T10-00-00-000Z_01900000-0000-7000-8000-000000000001"
    / "reviewer.jsonl"
)


@pytest.fixture
def connector() -> OmpConnector:
    return OmpConnector()


def _write_session(tmp_path: Path, name: str, lines: list[dict]) -> Path:
    slug_dir = tmp_path / "-tmp-demo-project"
    slug_dir.mkdir(parents=True, exist_ok=True)
    path = slug_dir / name
    path.write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")
    return path


class TestOmpCanParse:
    def test_can_parse_valid_session_filename(self, connector: OmpConnector) -> None:
        assert connector.can_parse(SESSION_1) is True

    def test_can_parse_rejects_non_jsonl(self, connector: OmpConnector, tmp_path: Path) -> None:
        path = tmp_path / "2026-03-29T10-00-00-000Z_01900000-0000-7000-8000-000000000001.txt"
        path.write_text("", encoding="utf-8")
        assert connector.can_parse(path) is False

    def test_can_parse_rejects_subagent_transcript_filename(self, connector: OmpConnector) -> None:
        # Nested per-tool-call / subagent transcripts never match the
        # `<timestamp>_<uuid>.jsonl` naming convention.
        assert connector.can_parse(NESTED_SUBAGENT) is False

    def test_can_parse_rejects_arbitrary_jsonl_name(self, connector: OmpConnector, tmp_path: Path) -> None:
        path = tmp_path / "notes.jsonl"
        path.write_text("{}", encoding="utf-8")
        assert connector.can_parse(path) is False


class TestOmpDiscoverFiles:
    def test_discover_files_finds_top_level_sessions_only(
        self, connector: OmpConnector, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            "searchat.core.connectors.omp.PathResolver.resolve_omp_dirs",
            staticmethod(lambda _config=None: [FIXTURES_ROOT.parent]),
        )
        files = connector.discover_files(Mock())
        assert set(files) == {SESSION_1, SESSION_2}
        assert NESTED_SUBAGENT not in files

    def test_discover_files_no_roots(self, connector: OmpConnector, monkeypatch) -> None:
        monkeypatch.setattr(
            "searchat.core.connectors.omp.PathResolver.resolve_omp_dirs",
            staticmethod(lambda _config=None: []),
        )
        assert connector.discover_files(Mock()) == []


class TestOmpParse:
    def test_parse_returns_conversation_record(self, connector: OmpConnector) -> None:
        record = connector.parse(SESSION_1, embedding_id=0)

        assert record.conversation_id == "01900000-0000-7000-8000-000000000001"
        assert record.project_id == "-tmp-demo-project"
        assert record.title == "Fix login bug"
        # m1 (user), m2 (assistant thinking+toolCall only -> no text -> skipped),
        # m3 (toolResult -> role "tool"), m4 (assistant with code block).
        assert record.message_count == 3
        roles = [m.role for m in record.messages]
        assert roles == ["user", "tool", "assistant"]
        assert record.messages[-1].has_code is True
        assert "authenticate(user)" in record.full_text

    def test_parse_skips_malformed_lines_and_maps_roles(self, connector: OmpConnector) -> None:
        record = connector.parse(SESSION_2, embedding_id=1)

        # n1 (developer -> system), n2 (user), n3 (bashExecution -> tool);
        # n4 (assistant, image-only content -> no text -> skipped); the
        # malformed raw line and the padded `title` event are both ignored.
        assert record.message_count == 3
        roles = [m.role for m in record.messages]
        assert roles == ["system", "user", "tool"]
        assert record.title == "Deploy script"

    def test_parse_falls_back_to_stem_and_mtime_without_session_line(
        self, connector: OmpConnector, tmp_path: Path
    ) -> None:
        path = _write_session(
            tmp_path,
            "2026-04-01T00-00-00-000Z_01900000-0000-7000-8000-0000000000aa.jsonl",
            [{"type": "message", "id": "x1", "message": {"role": "user", "content": [{"type": "text", "text": "hi"}]}}],
        )
        record = connector.parse(path, embedding_id=2)
        assert record.conversation_id == path.stem
        assert record.title == "hi"
        assert record.message_count == 1

    def test_parse_empty_file(self, connector: OmpConnector, tmp_path: Path) -> None:
        path = _write_session(tmp_path, "2026-04-01T00-00-00-000Z_01900000-0000-7000-8000-0000000000bb.jsonl", [])
        record = connector.parse(path, embedding_id=3)
        assert record.message_count == 0
        assert record.messages == []
        assert record.title == "Untitled omp Session"


class TestOmpLoadMessages:
    def test_load_messages_returns_normalized_roles(self, connector: OmpConnector) -> None:
        messages = connector.load_messages(SESSION_1)
        assert messages == [
            {"role": "user", "content": "Fix the login bug in auth.py"},
            {"role": "tool", "content": "def login(user):\n    pass"},
            {
                "role": "assistant",
                "content": "Found the bug: login() is a stub. Implementing it now.\n\n"
                "```python\ndef login(user):\n    return authenticate(user)\n```",
            },
        ]

    def test_load_messages_empty_file(self, connector: OmpConnector, tmp_path: Path) -> None:
        path = _write_session(tmp_path, "2026-04-01T00-00-00-000Z_01900000-0000-7000-8000-0000000000cc.jsonl", [])
        assert connector.load_messages(path) == []


class TestOmpExtractCwd:
    def test_extract_cwd(self, connector: OmpConnector) -> None:
        assert connector.extract_cwd(SESSION_1) == "/tmp/demo-project"

    def test_extract_cwd_missing_session_line(self, connector: OmpConnector, tmp_path: Path) -> None:
        path = _write_session(
            tmp_path,
            "2026-04-01T00-00-00-000Z_01900000-0000-7000-8000-0000000000dd.jsonl",
            [{"type": "message", "id": "x1", "message": {"role": "user", "content": [{"type": "text", "text": "hi"}]}}],
        )
        assert connector.extract_cwd(path) is None


class TestOmpBuildResumeCommand:
    def test_build_resume_command(self, connector: OmpConnector) -> None:
        cmd = connector.build_resume_command(SESSION_1)
        assert cmd == "omp --resume 01900000-0000-7000-8000-000000000001"

    def test_build_resume_command_no_session_line(self, connector: OmpConnector, tmp_path: Path) -> None:
        path = _write_session(
            tmp_path,
            "2026-04-01T00-00-00-000Z_01900000-0000-7000-8000-0000000000ee.jsonl",
            [{"type": "message", "id": "x1", "message": {"role": "user", "content": [{"type": "text", "text": "hi"}]}}],
        )
        assert connector.build_resume_command(path) is None
