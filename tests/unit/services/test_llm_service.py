from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from searchat.services.llm_service import LLMService


def test_llm_service_passes_temperature_and_max_tokens_to_litellm():
    cfg = SimpleNamespace(openai_model="gpt-4.1-mini", ollama_model="llama3")
    svc = LLMService(cfg)

    fake_response = {"choices": [{"message": {"content": "ok"}}]}

    with patch("litellm.completion", return_value=fake_response) as mock_completion:
        out = svc.completion(
            messages=[{"role": "user", "content": "hi"}],
            provider="openai",
            model_name="gpt-4.1-mini",
            temperature=0.7,
            max_tokens=123,
        )

    assert out == "ok"
    mock_completion.assert_called_once()
    _, kwargs = mock_completion.call_args
    assert kwargs["temperature"] == 0.7
    assert kwargs["max_tokens"] == 123
    assert kwargs["stream"] is False
