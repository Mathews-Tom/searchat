"""RAG pipeline for chat with history."""
from __future__ import annotations

from collections.abc import Iterator

from searchat.api.dependencies import get_search_engine
from searchat.config import Config
from searchat.models import SearchMode, SearchFilters, SearchResult
from searchat.services.llm_service import LLMService


SYSTEM_PROMPT = """
You are an intelligent knowledge assistant for a developer's personal archives.
You will be provided with "Context Chunks" retrieved from the user's past chat history.

**Instructions:**
1. Answer the user's question *only* using the provided Context Chunks.
2. If the answer is not in the chunks, state that you cannot find the information in the archives. Do not hallucinate.
3. **Citations:** When you state a fact, reference the date or conversation ID from the chunk (e.g., "[Date: 2023-10-12]" or "[Source: ID_123]").
4. Be concise and technical. The user is a developer.

**Context Chunks:**
{context_data}
""".strip()


def generate_answer_stream(
    query: str,
    provider: str,
    model_name: str | None,
    *,
    config: Config,
    top_k: int = 8,
) -> Iterator[str]:
    search_engine = get_search_engine()
    results = search_engine.search(query, mode=SearchMode.HYBRID, filters=SearchFilters())
    top_results = results.results[:top_k]

    if not top_results:
        yield "I cannot find the information in the archives."
        return

    context_data = _format_context(top_results)
    system_prompt = SYSTEM_PROMPT.format(context_data=context_data)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query},
    ]

    llm_service = LLMService(config.llm)
    yield from llm_service.stream_completion(
        messages=messages,
        provider=provider,
        model_name=model_name,
    )


def _format_context(results: list[SearchResult]) -> str:
    lines: list[str] = []
    for idx, result in enumerate(results, start=1):
        updated_at = result.updated_at.isoformat()
        lines.extend(
            [
                f"Chunk {idx}:",
                f"Source: {result.conversation_id}",
                f"Date: {updated_at}",
                f"Project: {result.project_id}",
                f"Snippet: {result.snippet}",
                "",
            ]
        )
    return "\n".join(lines).strip()
