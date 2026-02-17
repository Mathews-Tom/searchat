"""RAG pipeline for chat with history."""
from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass
from uuid import uuid4

from searchat.api.dependencies import get_search_engine
from searchat.config import Config
from searchat.config.constants import RAG_SYSTEM_PROMPT
from searchat.models import SearchMode, SearchFilters, SearchResult
from searchat.services.llm_service import LLMService


@dataclass
class ChatSession:
    """In-memory chat session with sliding window."""
    session_id: str
    messages: list[dict[str, str]]
    created_at: float
    last_active: float


_sessions: dict[str, ChatSession] = {}
_SESSION_TTL = 1800  # 30 minutes
_MAX_TURNS = 10  # Sliding window of turn pairs


def get_or_create_session(session_id: str | None) -> ChatSession:
    """Get existing session or create a new one."""
    _evict_expired()
    if session_id and session_id in _sessions:
        session = _sessions[session_id]
        session.last_active = time.time()
        return session
    new_id = uuid4().hex[:16]
    session = ChatSession(
        session_id=new_id,
        messages=[],
        created_at=time.time(),
        last_active=time.time(),
    )
    _sessions[new_id] = session
    return session


def _evict_expired() -> None:
    """Remove sessions that have exceeded TTL."""
    now = time.time()
    expired = [k for k, v in _sessions.items() if now - v.last_active > _SESSION_TTL]
    for k in expired:
        del _sessions[k]


def generate_answer_stream(
    query: str,
    provider: str,
    model_name: str | None,
    *,
    config: Config,
    top_k: int = 8,
    session_id: str | None = None,
) -> tuple[str, Iterator[str]]:
    """Generate streaming RAG answer. Returns (session_id, token_iterator)."""
    session = get_or_create_session(session_id)
    search_engine = get_search_engine()
    results = search_engine.search(query, mode=SearchMode.HYBRID, filters=SearchFilters())
    top_results = results.results[:top_k]

    if not top_results:
        def _empty():
            yield "I cannot find the information in the archives."
            session.messages.append({"role": "user", "content": query})
            session.messages.append({"role": "assistant", "content": "I cannot find the information in the archives."})
        return session.session_id, _empty()

    context_data = _format_context(top_results)
    system_prompt = RAG_SYSTEM_PROMPT.format(context_data=context_data)

    history = session.messages[-_MAX_TURNS * 2:]
    messages = [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": query},
    ]

    llm_service = LLMService(config.llm)

    def _stream():
        chunks: list[str] = []
        for chunk in llm_service.stream_completion(
            messages=messages,
            provider=provider,
            model_name=model_name,
        ):
            chunks.append(chunk)
            yield chunk
        # After streaming completes, update session
        full_answer = "".join(chunks)
        session.messages.append({"role": "user", "content": query})
        session.messages.append({"role": "assistant", "content": full_answer})

    return session.session_id, _stream()


@dataclass(frozen=True)
class RAGGeneration:
    """Generated non-streaming RAG response with source results."""

    answer: str
    results: list[SearchResult]
    context_used: int
    session_id: str = ""


def generate_rag_response(
    query: str,
    provider: str,
    model_name: str | None,
    *,
    config: Config,
    temperature: float | None = None,
    max_tokens: int | None = None,
    system_prompt: str | None = None,
    session_id: str | None = None,
) -> RAGGeneration:
    """Generate a grounded answer with structured sources (non-streaming)."""
    session = get_or_create_session(session_id)
    search_engine = get_search_engine()
    results = search_engine.search(query, mode=SearchMode.HYBRID, filters=SearchFilters())

    top_k = _select_top_k(query)
    top_results = results.results[:top_k]
    if not top_results:
        return RAGGeneration(
            answer="I cannot find the information in the archives.",
            results=[],
            context_used=0,
            session_id=session.session_id,
        )

    context_data = _format_context(top_results)
    system_content = RAG_SYSTEM_PROMPT.format(context_data=context_data)
    if system_prompt is not None and system_prompt.strip():
        system_content = system_prompt.strip() + "\n\nContext Chunks:\n" + context_data

    history = session.messages[-_MAX_TURNS * 2:]
    messages = [
        {"role": "system", "content": system_content},
        *history,
        {"role": "user", "content": query},
    ]

    llm_service = LLMService(config.llm)
    answer = llm_service.completion(
        messages=messages,
        provider=provider,
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    session.messages.append({"role": "user", "content": query})
    session.messages.append({"role": "assistant", "content": answer})

    return RAGGeneration(
        answer=answer,
        results=top_results,
        context_used=len(top_results),
        session_id=session.session_id,
    )


def _select_top_k(query: str) -> int:
    """Select number of context chunks based on query complexity."""

    q = query.strip().lower()
    if not q:
        return 8

    words = q.split()
    if len(words) <= 4:
        return 6

    complexity_terms = (
        "summarize",
        "summary",
        "compare",
        "difference",
        "timeline",
        "history",
        "root cause",
        "postmortem",
        "design",
        "architecture",
        "plan",
        "steps",
        "why",
        "how",
        "tradeoff",
        "trade-off",
        "proposal",
    )

    is_complex = (
        len(words) >= 18
        or "\n" in query
        or any(term in q for term in complexity_terms)
        or q.count("?") >= 2
    )

    if is_complex:
        return 16
    return 8


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
