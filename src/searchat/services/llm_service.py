"""LLM gateway service using LiteLLM."""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from searchat.config.settings import LLMConfig


class LLMServiceError(RuntimeError):
    """Raised when the LLM provider fails."""


class LLMService:
    """LLM wrapper supporting remote and local providers."""

    def __init__(self, config: LLMConfig) -> None:
        self._config = config

    def stream_completion(
        self,
        *,
        messages: list[dict[str, str]],
        provider: str,
        model_name: str | None = None,
    ) -> Iterator[str]:
        from litellm import completion

        model = self._resolve_model(provider, model_name)
        try:
            response = completion(model=model, messages=messages, stream=True)
        except Exception as exc:
            raise self._wrap_error(provider, exc) from exc

        for chunk in response:
            content = _extract_chunk_text(chunk)
            if content:
                yield content

    def completion(
        self,
        *,
        messages: list[dict[str, str]],
        provider: str,
        model_name: str | None = None,
    ) -> str:
        from litellm import completion

        model = self._resolve_model(provider, model_name)
        try:
            response = completion(model=model, messages=messages, stream=False)
        except Exception as exc:
            raise self._wrap_error(provider, exc) from exc

        content = _extract_response_text(response)
        if not content:
            raise LLMServiceError("LLM response contained no content.")
        return content

    def _resolve_model(self, provider: str, model_name: str | None) -> str:
        provider_value = provider.lower()
        if provider_value not in ("openai", "ollama"):
            raise ValueError("model_provider must be 'openai' or 'ollama'.")

        resolved = model_name
        if resolved is None:
            if provider_value == "openai":
                resolved = self._config.openai_model
            else:
                resolved = self._config.ollama_model

        if not resolved:
            raise ValueError("model_name must be provided or configured for this provider.")

        if provider_value == "ollama" and not resolved.startswith("ollama/"):
            return f"ollama/{resolved}"

        return resolved

    def _wrap_error(self, provider: str, exc: Exception) -> LLMServiceError:
        provider_value = provider.lower()
        if provider_value == "ollama":
            return LLMServiceError("Ollama provider unreachable or returned an error.")
        return LLMServiceError("LLM request failed.")


def _extract_chunk_text(chunk: Any) -> str:
    if isinstance(chunk, dict):
        choices = chunk.get("choices") or []
    else:
        choices = getattr(chunk, "choices", []) or []

    if not choices:
        return ""

    first = choices[0]
    if isinstance(first, dict):
        delta = first.get("delta") or first.get("message") or {}
        return delta.get("content") or first.get("text") or ""

    delta = getattr(first, "delta", None) or getattr(first, "message", None)
    if delta is not None:
        return getattr(delta, "content", "") or ""
    return getattr(first, "text", "") or ""


def _extract_response_text(response: Any) -> str:
    if isinstance(response, dict):
        choices = response.get("choices") or []
    else:
        choices = getattr(response, "choices", []) or []

    if not choices:
        return ""

    first = choices[0]
    if isinstance(first, dict):
        message = first.get("message") or {}
        return message.get("content") or first.get("text") or ""

    message = getattr(first, "message", None)
    if message is not None:
        return getattr(message, "content", "") or ""
    return getattr(first, "text", "") or ""
