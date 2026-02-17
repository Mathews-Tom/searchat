"""Tests for searchat.services.llm_service."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from searchat.services.llm_service import (
    LLMService,
    LLMServiceError,
    _extract_chunk_text,
    _extract_response_text,
)


@pytest.fixture
def llm_config() -> SimpleNamespace:
    return SimpleNamespace(openai_model="gpt-4.1-mini", ollama_model="llama3")


@pytest.fixture
def svc(llm_config: SimpleNamespace) -> LLMService:
    return LLMService(llm_config)


# ── completion() ────────────────────────────────────────────────────

def test_completion_passes_temperature_and_max_tokens(svc: LLMService):
    response = {"choices": [{"message": {"content": "ok"}}]}
    with patch("litellm.completion", return_value=response) as mock_comp:
        out = svc.completion(
            messages=[{"role": "user", "content": "hi"}],
            provider="openai",
            model_name="gpt-4.1-mini",
            temperature=0.7,
            max_tokens=123,
        )
    assert out == "ok"
    _, kwargs = mock_comp.call_args
    assert kwargs["temperature"] == 0.7
    assert kwargs["max_tokens"] == 123
    assert kwargs["stream"] is False


def test_completion_embedded_delegates(svc: LLMService):
    with patch.object(svc, "_embedded_completion", return_value="embedded reply") as mock_emb:
        out = svc.completion(
            messages=[{"role": "user", "content": "hi"}],
            provider="embedded",
            model_name="model.gguf",
            temperature=0.5,
            max_tokens=100,
        )
    assert out == "embedded reply"
    mock_emb.assert_called_once_with(
        messages=[{"role": "user", "content": "hi"}],
        model_path_override="model.gguf",
        temperature=0.5,
        max_tokens=100,
    )


def test_completion_error_wrapping(svc: LLMService):
    with patch("litellm.completion", side_effect=ConnectionError("refused")):
        with pytest.raises(LLMServiceError, match="LLM request failed"):
            svc.completion(
                messages=[{"role": "user", "content": "hi"}],
                provider="openai",
            )


def test_completion_empty_response_raises(svc: LLMService):
    response = {"choices": []}
    with patch("litellm.completion", return_value=response):
        with pytest.raises(LLMServiceError, match="no content"):
            svc.completion(
                messages=[{"role": "user", "content": "hi"}],
                provider="openai",
            )


# ── stream_completion() ────────────────────────────────────────────

def test_stream_completion_yields_chunks(svc: LLMService):
    chunks = [
        {"choices": [{"delta": {"content": "hel"}}]},
        {"choices": [{"delta": {"content": "lo"}}]},
    ]
    with patch("litellm.completion", return_value=iter(chunks)):
        result = list(svc.stream_completion(
            messages=[{"role": "user", "content": "hi"}],
            provider="openai",
        ))
    assert result == ["hel", "lo"]


def test_stream_completion_embedded_delegates(svc: LLMService):
    with patch.object(svc, "_embedded_stream", return_value=iter(["a", "b"])):
        result = list(svc.stream_completion(
            messages=[{"role": "user", "content": "hi"}],
            provider="embedded",
        ))
    assert result == ["a", "b"]


def test_stream_completion_error_wrapping(svc: LLMService):
    with patch("litellm.completion", side_effect=ConnectionError("refused")):
        with pytest.raises(LLMServiceError, match="LLM request failed"):
            list(svc.stream_completion(
                messages=[{"role": "user", "content": "hi"}],
                provider="openai",
            ))


# ── _resolve_model() ───────────────────────────────────────────────

def test_resolve_model_openai_default(svc: LLMService):
    assert svc._resolve_model("openai", None) == "gpt-4.1-mini"


def test_resolve_model_ollama_default_prefixed(svc: LLMService):
    assert svc._resolve_model("ollama", None) == "ollama/llama3"


def test_resolve_model_ollama_already_prefixed(svc: LLMService):
    assert svc._resolve_model("ollama", "ollama/custom") == "ollama/custom"


def test_resolve_model_invalid_provider(svc: LLMService):
    with pytest.raises(ValueError, match="openai.*ollama.*embedded"):
        svc._resolve_model("azure", None)


def test_resolve_model_empty_raises(llm_config: SimpleNamespace):
    llm_config.openai_model = ""
    s = LLMService(llm_config)
    with pytest.raises(ValueError, match="must be provided or configured"):
        s._resolve_model("openai", None)


# ── _wrap_error() ──────────────────────────────────────────────────

def test_wrap_error_ollama(svc: LLMService):
    err = svc._wrap_error("ollama", RuntimeError("boom"))
    assert "Ollama" in str(err)


def test_wrap_error_embedded(svc: LLMService):
    err = svc._wrap_error("embedded", RuntimeError("model not found"))
    assert "model not found" in str(err)


def test_wrap_error_generic(svc: LLMService):
    err = svc._wrap_error("openai", RuntimeError("timeout"))
    assert "LLM request failed" in str(err)


# ── _extract_chunk_text() ─────────────────────────────────────────

def test_extract_chunk_dict_delta_content():
    chunk = {"choices": [{"delta": {"content": "hello"}}]}
    assert _extract_chunk_text(chunk) == "hello"


def test_extract_chunk_dict_text_field():
    chunk = {"choices": [{"text": "world"}]}
    assert _extract_chunk_text(chunk) == "world"


def test_extract_chunk_object_with_delta():
    delta = SimpleNamespace(content="obj")
    choice = SimpleNamespace(delta=delta, message=None, text=None)
    chunk = SimpleNamespace(choices=[choice])
    assert _extract_chunk_text(chunk) == "obj"


def test_extract_chunk_empty_choices():
    assert _extract_chunk_text({"choices": []}) == ""
    assert _extract_chunk_text({"choices": None}) == ""


def test_extract_chunk_object_text_fallback():
    choice = SimpleNamespace(delta=None, message=None, text="fallback")
    chunk = SimpleNamespace(choices=[choice])
    assert _extract_chunk_text(chunk) == "fallback"


# ── _extract_response_text() ──────────────────────────────────────

def test_extract_response_dict_message_content():
    resp = {"choices": [{"message": {"content": "answer"}}]}
    assert _extract_response_text(resp) == "answer"


def test_extract_response_dict_text_field():
    resp = {"choices": [{"text": "txt"}]}
    assert _extract_response_text(resp) == "txt"


def test_extract_response_object_message():
    msg = SimpleNamespace(content="obj_answer")
    choice = SimpleNamespace(message=msg, text=None)
    resp = SimpleNamespace(choices=[choice])
    assert _extract_response_text(resp) == "obj_answer"


def test_extract_response_empty_choices():
    assert _extract_response_text({"choices": []}) == ""
    assert _extract_response_text({"choices": None}) == ""


def test_extract_response_object_text_fallback():
    choice = SimpleNamespace(message=None, text="fb")
    resp = SimpleNamespace(choices=[choice])
    assert _extract_response_text(resp) == "fb"


# ── _embedded_completion / _embedded_stream error wrapping ─────────

def test_embedded_completion_wraps_error(svc: LLMService):
    with patch(
        "searchat.llm.embedded_provider.embedded_completion",
        side_effect=RuntimeError("model load failed"),
    ):
        with pytest.raises(LLMServiceError, match="model load failed"):
            svc.completion(
                messages=[{"role": "user", "content": "hi"}],
                provider="embedded",
            )


def test_embedded_stream_wraps_error(svc: LLMService):
    with patch(
        "searchat.llm.embedded_provider.embedded_stream_completion",
        side_effect=RuntimeError("model load failed"),
    ):
        with pytest.raises(LLMServiceError, match="model load failed"):
            list(svc.stream_completion(
                messages=[{"role": "user", "content": "hi"}],
                provider="embedded",
            ))
