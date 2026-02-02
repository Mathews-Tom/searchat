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
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        provider_value = provider.lower()
        if provider_value == "embedded":
            yield from self._embedded_stream(
                messages=messages,
                model_path_override=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return

        from litellm import completion

        model = self._resolve_model(provider_value, model_name)
        extra: dict[str, Any] = {}
        if temperature is not None:
            extra["temperature"] = temperature
        if max_tokens is not None:
            extra["max_tokens"] = max_tokens
        try:
            response = completion(model=model, messages=messages, stream=True, **extra)
        except Exception as exc:
            raise self._wrap_error(provider_value, exc) from exc

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
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        provider_value = provider.lower()
        if provider_value == "embedded":
            return self._embedded_completion(
                messages=messages,
                model_path_override=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        from litellm import completion

        model = self._resolve_model(provider_value, model_name)
        extra: dict[str, Any] = {}
        if temperature is not None:
            extra["temperature"] = temperature
        if max_tokens is not None:
            extra["max_tokens"] = max_tokens
        try:
            response = completion(model=model, messages=messages, stream=False, **extra)
        except Exception as exc:
            raise self._wrap_error(provider_value, exc) from exc

        content = _extract_response_text(response)
        if not content:
            raise LLMServiceError("LLM response contained no content.")
        return content

    def _resolve_model(self, provider_value: str, model_name: str | None) -> str:
        if provider_value not in ("openai", "ollama"):
            raise ValueError("model_provider must be 'openai' or 'ollama' or 'embedded'.")

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

    def _wrap_error(self, provider_value: str, exc: Exception) -> LLMServiceError:
        if provider_value == "ollama":
            return LLMServiceError("Ollama provider unreachable or returned an error.")
        if provider_value == "embedded":
            return LLMServiceError(str(exc))
        return LLMServiceError("LLM request failed.")

    def _embedded_completion(
        self,
        *,
        messages: list[dict[str, str]],
        model_path_override: str | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> str:
        from searchat.llm.embedded_provider import embedded_completion

        try:
            return embedded_completion(
                messages=messages,
                config=self._config,
                model_path_override=model_path_override,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            raise self._wrap_error("embedded", exc) from exc

    def _embedded_stream(
        self,
        *,
        messages: list[dict[str, str]],
        model_path_override: str | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> Iterator[str]:
        from searchat.llm.embedded_provider import embedded_stream_completion

        try:
            yield from embedded_stream_completion(
                messages=messages,
                config=self._config,
                model_path_override=model_path_override,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            raise self._wrap_error("embedded", exc) from exc


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
