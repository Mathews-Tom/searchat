"""Tests for palace LLM module."""
from __future__ import annotations

import json

from unittest.mock import patch

import pytest

from searchat.palace.llm import (
    CLIDistillationLLM,
    DistillationInput,
    DistillationOutput,
    RoomAssignment,
)


class TestParseResponse:
    def _parse(self, raw: str) -> DistillationOutput:
        llm = CLIDistillationLLM.__new__(CLIDistillationLLM)
        return llm._parse_response(raw)

    def test_parse_valid_json(self):
        data = {
            "exchange_core": "Fixed the bug",
            "specific_context": "Error on line 42",
            "room_assignments": [{
                "room_type": "file",
                "room_key": "auth",
                "room_label": "Auth Module",
                "relevance": 0.9,
            }],
        }
        result = self._parse(json.dumps(data))
        assert result.exchange_core == "Fixed the bug"
        assert result.specific_context == "Error on line 42"
        assert len(result.room_assignments) == 1
        assert result.room_assignments[0].room_type == "file"
        assert result.room_assignments[0].relevance == 0.9

    def test_parse_fenced_json(self):
        data = {
            "exchange_core": "Added pooling",
            "specific_context": "Pool size 20",
            "room_assignments": [],
        }
        raw = f"```json\n{json.dumps(data)}\n```"
        result = self._parse(raw)
        assert result.exchange_core == "Added pooling"

    def test_parse_invalid_json(self):
        with pytest.raises(RuntimeError, match="Malformed JSON"):
            self._parse("not json at all")

    def test_parse_non_dict_json(self):
        with pytest.raises(RuntimeError, match="Expected JSON object"):
            self._parse("[1, 2, 3]")

    def test_parse_no_room_assignments(self):
        data = {
            "exchange_core": "Simple fix",
            "specific_context": "Line 10",
        }
        result = self._parse(json.dumps(data))
        assert result.room_assignments == []


class TestFormatFailureOutput:
    def test_stderr_only(self):
        result = CLIDistillationLLM._format_failure_output(stdout="", stderr="error msg")
        assert "error msg" in result

    def test_stdout_only(self):
        result = CLIDistillationLLM._format_failure_output(stdout="output", stderr="")
        assert "output" in result

    def test_both(self):
        result = CLIDistillationLLM._format_failure_output(stdout="out", stderr="err")
        assert "err" in result
        assert "out" in result

    def test_none(self):
        result = CLIDistillationLLM._format_failure_output(stdout="", stderr="")
        assert "no stdout" in result


class TestResolveProvider:
    def test_auto_no_cli_raises(self):
        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="No distillation CLI found"):
                CLIDistillationLLM._resolve_provider("auto", "claude-haiku-4-5-20251001")

    def test_pick_model_matching_provider(self):
        model = CLIDistillationLLM._pick_model("claude", "claude-haiku-4-5-20251001")
        assert model == "claude-haiku-4-5-20251001"

    def test_pick_model_mismatched_uses_default(self):
        model = CLIDistillationLLM._pick_model("openai", "claude-haiku-4-5-20251001")
        assert model.startswith("gpt-")


class TestDistillationInput:
    def test_creation(self):
        inp = DistillationInput(
            conversation_id="conv-1",
            project_id="proj-1",
            messages=[{"role": "user", "content": "test"}],
            ply_start=0,
            ply_end=1,
        )
        assert inp.conversation_id == "conv-1"
        assert len(inp.messages) == 1
