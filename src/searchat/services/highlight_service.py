"""LLM-driven term extraction for search highlighting."""
from __future__ import annotations

import json

from searchat.config import Config
from searchat.services.llm_service import LLMService


SYSTEM_PROMPT = """
Extract concise highlight terms for the given search query.

Return a JSON array of strings with 3-8 short terms or phrases.
- Do not include the full query verbatim unless it is a short phrase.
- Prefer nouns, key entities, or concepts.
- No extra text, no markdown, JSON only.
""".strip()


def extract_highlight_terms(
    *,
    query: str,
    provider: str,
    model_name: str | None,
    config: Config,
) -> list[str]:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ]
    llm_service = LLMService(config.llm)
    response_text = llm_service.completion(
        messages=messages,
        provider=provider,
        model_name=model_name,
    )
    return _parse_terms(response_text)


def _parse_terms(text: str) -> list[str]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError("LLM highlight response must be valid JSON array.") from exc

    if not isinstance(parsed, list):
        raise ValueError("LLM highlight response must be a JSON array.")

    terms: list[str] = []
    seen = set()
    for item in parsed:
        if not isinstance(item, str):
            raise ValueError("LLM highlight array must contain strings only.")
        term = item.strip()
        if not term:
            continue
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        terms.append(term)

    if not terms:
        raise ValueError("LLM highlight response contained no usable terms.")

    return terms[:8]
