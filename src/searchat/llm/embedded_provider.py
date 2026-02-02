from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from searchat.config.settings import LLMConfig


class EmbeddedProviderError(RuntimeError):
    """Raised when the embedded provider cannot run."""


@dataclass(frozen=True)
class _EmbeddedModelKey:
    path: str
    n_ctx: int
    n_threads: int


_MODEL_LOCK = Lock()
_MODEL_KEY: _EmbeddedModelKey | None = None
_MODEL: Any | None = None


def embedded_completion(
    *,
    messages: list[dict[str, str]],
    config: LLMConfig,
    model_path_override: str | None,
    temperature: float | None,
    max_tokens: int | None,
) -> str:
    model = _get_model(config=config, model_path_override=model_path_override)
    extra: dict[str, Any] = {}
    if temperature is not None:
        extra["temperature"] = temperature
    if max_tokens is not None:
        extra["max_tokens"] = max_tokens

    try:
        resp = model.create_chat_completion(messages=messages, stream=False, **extra)
    except Exception as exc:
        raise EmbeddedProviderError(str(exc)) from exc

    return _extract_text_from_chat_response(resp)


def embedded_stream_completion(
    *,
    messages: list[dict[str, str]],
    config: LLMConfig,
    model_path_override: str | None,
    temperature: float | None,
    max_tokens: int | None,
) -> Iterator[str]:
    model = _get_model(config=config, model_path_override=model_path_override)
    extra: dict[str, Any] = {}
    if temperature is not None:
        extra["temperature"] = temperature
    if max_tokens is not None:
        extra["max_tokens"] = max_tokens

    try:
        stream = model.create_chat_completion(messages=messages, stream=True, **extra)
    except Exception as exc:
        raise EmbeddedProviderError(str(exc)) from exc

    for chunk in stream:
        text = _extract_text_from_stream_chunk(chunk)
        if text:
            yield text


def _get_model(*, config: LLMConfig, model_path_override: str | None) -> Any:
    global _MODEL, _MODEL_KEY

    model_path = _resolve_model_path(config=config, model_path_override=model_path_override)

    n_ctx = int(config.embedded_n_ctx)
    n_threads = int(config.embedded_n_threads)
    if n_ctx <= 0:
        raise EmbeddedProviderError("embedded_n_ctx must be > 0")

    key = _EmbeddedModelKey(path=str(model_path), n_ctx=n_ctx, n_threads=n_threads)
    with _MODEL_LOCK:
        if _MODEL is not None and _MODEL_KEY == key:
            return _MODEL

        try:
            from llama_cpp import Llama
        except Exception as exc:
            raise EmbeddedProviderError(
                "Embedded provider requires 'llama-cpp-python'. Install with: pip install 'searchat[embedded]'"
            ) from exc

        kwargs: dict[str, Any] = {"model_path": str(model_path), "n_ctx": n_ctx}
        if n_threads > 0:
            kwargs["n_threads"] = n_threads

        try:
            _MODEL = Llama(**kwargs)
        except Exception as exc:
            raise EmbeddedProviderError(f"Failed to load embedded model: {exc}") from exc

        _MODEL_KEY = key
        return _MODEL


def _resolve_model_path(*, config: LLMConfig, model_path_override: str | None) -> Path:
    raw = model_path_override or config.embedded_model_path
    if not raw:
        raise EmbeddedProviderError(
            "embedded_model_path is not configured. Set [llm].embedded_model_path or run 'searchat download-model --activate'."
        )
    path = Path(raw).expanduser()
    if not path.exists():
        raise EmbeddedProviderError(f"Embedded model not found: {path}")
    if not path.is_file():
        raise EmbeddedProviderError(f"Embedded model path is not a file: {path}")
    return path


def _extract_text_from_chat_response(resp: Any) -> str:
    if isinstance(resp, dict):
        choices = resp.get("choices") or []
    else:
        choices = getattr(resp, "choices", []) or []

    if not choices:
        raise EmbeddedProviderError("Embedded model returned no choices")

    first = choices[0]
    if isinstance(first, dict):
        message = first.get("message") or {}
        content = message.get("content")
        if isinstance(content, str) and content:
            return content
        text = first.get("text")
        if isinstance(text, str) and text:
            return text
    else:
        message = getattr(first, "message", None)
        if message is not None:
            content = getattr(message, "content", "")
            if content:
                return str(content)
        text = getattr(first, "text", "")
        if text:
            return str(text)

    raise EmbeddedProviderError("Embedded model response contained no content")


def _extract_text_from_stream_chunk(chunk: Any) -> str:
    if isinstance(chunk, dict):
        choices = chunk.get("choices") or []
    else:
        choices = getattr(chunk, "choices", []) or []

    if not choices:
        return ""

    first = choices[0]
    if isinstance(first, dict):
        delta = first.get("delta") or first.get("message") or {}
        content = delta.get("content")
        if isinstance(content, str):
            return content
        text = first.get("text")
        if isinstance(text, str):
            return text
        return ""

    delta = getattr(first, "delta", None) or getattr(first, "message", None)
    if delta is not None:
        content = getattr(delta, "content", "")
        if content:
            return str(content)
    text = getattr(first, "text", "")
    if text:
        return str(text)
    return ""
