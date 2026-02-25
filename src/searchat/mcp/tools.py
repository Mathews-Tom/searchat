from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from searchat.api.duckdb_store import DuckDBStore
from searchat.api.utils import detect_tool_from_path
from searchat.config import Config, PathResolver
from searchat.config.constants import VALID_TOOL_NAMES, RAG_SYSTEM_PROMPT
from searchat.core.search_engine import SearchEngine
from searchat.models import SearchFilters, SearchMode
from searchat.services.llm_service import LLMService

from typing import cast, Any


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _json_dumps(payload: object) -> str:
    return json.dumps(payload, default=_json_default, ensure_ascii=True)


def resolve_dataset(search_dir: str | None) -> Path:
    config = Config.load()
    base_dir = PathResolver.get_shared_search_dir(config)
    if search_dir is None or not str(search_dir).strip():
        return base_dir
    resolved = Path(str(search_dir)).expanduser()
    if not resolved.exists():
        raise FileNotFoundError(f"Search directory does not exist: {resolved}")
    return resolved


def build_services(search_dir: Path) -> tuple[Config, SearchEngine, DuckDBStore]:
    config = Config.load()
    engine = SearchEngine(search_dir, config)
    store = DuckDBStore(search_dir, memory_limit_mb=config.performance.memory_limit_mb)
    return config, engine, store


def parse_mode(mode: str) -> SearchMode:
    value = (mode or "").lower().strip()
    if value == "hybrid":
        return SearchMode.HYBRID
    if value == "semantic":
        return SearchMode.SEMANTIC
    if value == "keyword":
        return SearchMode.KEYWORD
    raise ValueError("Invalid mode; expected: hybrid, semantic, keyword")


def parse_tool(tool: str | None) -> str | None:
    if tool is None:
        return None
    value = tool.lower().strip()
    if not value:
        return None
    if value not in VALID_TOOL_NAMES:
        raise ValueError(f"Invalid tool; expected one of: {', '.join(sorted(VALID_TOOL_NAMES))}")
    return value


def search_conversations(
    *,
    query: str,
    mode: str = "hybrid",
    project_id: str | None = None,
    tool: str | None = None,
    limit: int = 10,
    offset: int = 0,
    search_dir: str | None = None,
) -> str:
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")
    if offset < 0:
        raise ValueError("offset must be >= 0")

    dataset_dir = resolve_dataset(search_dir)
    _config, engine, _store = build_services(dataset_dir)

    filters = SearchFilters()
    if project_id:
        filters.project_ids = [project_id]

    tool_value = parse_tool(tool)
    if tool_value is not None:
        filters.tool = tool_value

    results = engine.search(query, mode=parse_mode(mode), filters=filters)

    sliced = results.results[offset : offset + limit]
    payload = {
        "results": [
            {
                "conversation_id": r.conversation_id,
                "project_id": r.project_id,
                "title": r.title,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
                "message_count": r.message_count,
                "file_path": r.file_path,
                "snippet": r.snippet,
                "score": r.score,
                "message_start_index": r.message_start_index,
                "message_end_index": r.message_end_index,
            }
            for r in sliced
        ],
        "total": len(results.results),
        "limit": limit,
        "offset": offset,
        "mode_used": results.mode_used,
        "search_time_ms": results.search_time_ms,
    }
    return _json_dumps(payload)


def get_conversation(*, conversation_id: str, search_dir: str | None = None) -> str:
    dataset_dir = resolve_dataset(search_dir)
    _config, _engine, store = build_services(dataset_dir)

    record = store.get_conversation_record(conversation_id)
    if record is None:
        raise ValueError(f"Conversation not found: {conversation_id}")

    return _json_dumps(record)


def list_projects(*, search_dir: str | None = None) -> str:
    dataset_dir = resolve_dataset(search_dir)
    _config, _engine, store = build_services(dataset_dir)
    return _json_dumps({"projects": store.list_projects()})


def get_statistics(*, search_dir: str | None = None) -> str:
    dataset_dir = resolve_dataset(search_dir)
    _config, _engine, store = build_services(dataset_dir)
    stats = store.get_statistics()
    return _json_dumps(
        {
            "total_conversations": stats.total_conversations,
            "total_messages": stats.total_messages,
            "avg_messages": stats.avg_messages,
            "total_projects": stats.total_projects,
            "earliest_date": stats.earliest_date,
            "latest_date": stats.latest_date,
        }
    )


def find_similar_conversations(
    *,
    conversation_id: str,
    limit: int = 5,
    search_dir: str | None = None,
) -> str:
    if limit < 1 or limit > 20:
        raise ValueError("limit must be between 1 and 20")

    dataset_dir = resolve_dataset(search_dir)
    _config, engine, store = build_services(dataset_dir)

    conv_meta = store.get_conversation_meta(conversation_id)
    if not conv_meta:
        raise ValueError(f"Conversation not found: {conversation_id}")

    engine.ensure_faiss_loaded()
    engine.ensure_embedder_loaded()
    if engine.faiss_index is None or engine.embedder is None:
        raise RuntimeError("Semantic components not available")

    con = store._connect()
    try:
        row = con.execute(
            """
            SELECT chunk_text
            FROM parquet_scan(?)
            WHERE conversation_id = ?
            ORDER BY vector_id
            LIMIT 1
            """,
            [str(engine.metadata_path), conversation_id],
        ).fetchone()
    finally:
        con.close()

    if row is None:
        raise ValueError("No embeddings found for this conversation")

    chunk_text = row[0]
    representative_text = f"{conv_meta['title']} {chunk_text}"

    import numpy as np

    query_embedding = np.asarray(engine.embedder.encode(representative_text), dtype=np.float32)
    k = limit + 10
    faiss_index = cast(Any, engine.faiss_index)
    distances, labels = faiss_index.search(query_embedding.reshape(1, -1), k)

    valid_mask = labels[0] >= 0
    hits: list[tuple[int, float]] = []
    for vid, distance in zip(labels[0][valid_mask], distances[0][valid_mask]):
        hits.append((int(vid), float(distance)))

    if not hits:
        return _json_dumps({"conversation_id": conversation_id, "similar_conversations": []})

    values_clause = ", ".join(["(?, ?)"] * len(hits))
    params: list[object] = []
    for vid, distance in hits:
        params.extend([vid, distance])
    params.append(str(engine.metadata_path))
    params.append(engine.conversations_glob)
    params.append(conversation_id)
    params.append(limit)

    con = store._connect()
    try:
        sql = f"""
            WITH hits(vector_id, distance) AS (
                VALUES {values_clause}
            )
            SELECT
                m.conversation_id,
                c.project_id,
                c.title,
                c.created_at,
                c.updated_at,
                c.message_count,
                c.file_path,
                hits.distance
            FROM hits
            JOIN parquet_scan(?) AS m
                ON m.vector_id = hits.vector_id
            JOIN (
                SELECT *
                FROM parquet_scan(?)
                QUALIFY row_number() OVER (
                    PARTITION BY conversation_id ORDER BY updated_at DESC
                ) = 1
            ) AS c
                ON c.conversation_id = m.conversation_id
            WHERE m.conversation_id != ?
            QUALIFY row_number() OVER (PARTITION BY m.conversation_id ORDER BY hits.distance) = 1
            ORDER BY hits.distance
            LIMIT ?
        """
        rows = con.execute(sql, params).fetchall()
    finally:
        con.close()

    similar: list[dict[str, object]] = []
    for (
        sim_id,
        project_id,
        title,
        created_at,
        updated_at,
        message_count,
        file_path,
        distance,
    ) in rows:
        score = 1.0 / (1.0 + float(distance))
        created_at_str = created_at if isinstance(created_at, str) else created_at.isoformat()
        updated_at_str = updated_at if isinstance(updated_at, str) else updated_at.isoformat()
        similar.append(
            {
                "conversation_id": sim_id,
                "project_id": project_id,
                "title": title,
                "created_at": created_at_str,
                "updated_at": updated_at_str,
                "message_count": message_count,
                "similarity_score": round(score, 3),
                "tool": detect_tool_from_path(file_path),
            }
        )

    return _json_dumps(
        {
            "conversation_id": conversation_id,
            "title": conv_meta.get("title"),
            "similar_count": len(similar),
            "similar_conversations": similar,
        }
    )


def ask_about_history(
    *,
    question: str,
    include_sources: bool = True,
    model_provider: str | None = None,
    model_name: str | None = None,
    search_dir: str | None = None,
) -> str:
    dataset_dir = resolve_dataset(search_dir)
    config, engine, _store = build_services(dataset_dir)

    provider = (model_provider or config.llm.default_provider or "ollama").lower().strip()
    if provider not in ("openai", "ollama", "embedded"):
        raise ValueError("model_provider must be one of: openai, ollama, embedded")

    results = engine.search(question, mode=SearchMode.HYBRID, filters=SearchFilters())
    top_results = results.results[:8]
    if not top_results:
        payload: dict[str, object] = {"answer": "I cannot find the information in the archives."}
        if include_sources:
            payload["sources"] = []
        return _json_dumps(payload)

    context_lines: list[str] = []
    for idx, r in enumerate(top_results, start=1):
        updated_at = r.updated_at.isoformat()
        context_lines.extend(
            [
                f"Chunk {idx}:",
                f"Source: {r.conversation_id}",
                f"Date: {updated_at}",
                f"Project: {r.project_id}",
                f"Snippet: {r.snippet}",
                "",
            ]
        )
    context_data = "\n".join(context_lines).strip()

    messages = [
        {"role": "system", "content": RAG_SYSTEM_PROMPT.format(context_data=context_data)},
        {"role": "user", "content": question},
    ]

    llm = LLMService(config.llm)
    answer = llm.completion(messages=messages, provider=provider, model_name=model_name)

    payload: dict[str, object] = {"answer": answer}
    if include_sources:
        payload["sources"] = [
            {
                "conversation_id": r.conversation_id,
                "project_id": r.project_id,
                "title": r.title,
                "score": r.score,
                "snippet": r.snippet,
                "message_start_index": r.message_start_index,
                "message_end_index": r.message_end_index,
                "tool": detect_tool_from_path(r.file_path),
            }
            for r in top_results
        ]
    return _json_dumps(payload)


def extract_patterns(
    *,
    topic: str | None = None,
    max_patterns: int = 10,
    model_provider: str | None = None,
    model_name: str | None = None,
    search_dir: str | None = None,
) -> str:
    """Extract recurring patterns from conversation history.

    Mines the conversation archive for coding conventions, architecture decisions,
    and recurring patterns using semantic search and LLM synthesis.
    """
    from searchat.services.pattern_mining import extract_patterns as _extract_patterns

    dataset_dir = resolve_dataset(search_dir)
    config, _engine, _store = build_services(dataset_dir)

    provider = (model_provider or config.llm.default_provider or "ollama").lower().strip()
    if provider not in ("openai", "ollama", "embedded"):
        raise ValueError("model_provider must be one of: openai, ollama, embedded")

    patterns = _extract_patterns(
        topic=topic,
        max_patterns=max_patterns,
        model_provider=provider,
        model_name=model_name,
        config=config,
    )

    return _json_dumps({
        "patterns": [
            {
                "name": p.name,
                "description": p.description,
                "confidence": p.confidence,
                "evidence": [
                    {
                        "conversation_id": e.conversation_id,
                        "date": e.date,
                        "snippet": e.snippet,
                    }
                    for e in p.evidence
                ],
            }
            for p in patterns
        ],
        "total": len(patterns),
    })


def generate_agent_config(
    *,
    format: str = "claude.md",
    project_filter: str | None = None,
    model_provider: str | None = None,
    model_name: str | None = None,
    search_dir: str | None = None,
) -> str:
    """Generate agent configuration file from conversation patterns.

    Extracts patterns from conversation history and formats them into
    an agent config file (CLAUDE.md, copilot-instructions.md, or cursorrules).
    """
    from searchat.services.pattern_mining import extract_patterns as _extract_patterns
    from searchat.config.constants import AGENT_CONFIG_TEMPLATES

    if format not in ("claude.md", "copilot-instructions.md", "cursorrules"):
        raise ValueError("format must be one of: claude.md, copilot-instructions.md, cursorrules")

    dataset_dir = resolve_dataset(search_dir)
    config, _engine, _store = build_services(dataset_dir)

    provider = (model_provider or config.llm.default_provider or "ollama").lower().strip()
    if provider not in ("openai", "ollama", "embedded"):
        raise ValueError("model_provider must be one of: openai, ollama, embedded")

    patterns = _extract_patterns(
        topic=project_filter,
        max_patterns=15,
        model_provider=provider,
        model_name=model_name,
        config=config,
    )

    pattern_lines: list[str] = []
    for p in patterns:
        pattern_lines.append(f"### {p.name}")
        pattern_lines.append(f"{p.description}")
        if p.evidence:
            pattern_lines.append("")
            pattern_lines.append("Evidence:")
            for e in p.evidence[:3]:
                pattern_lines.append(f"- [{e.date}] {e.snippet[:100]}...")
        pattern_lines.append("")

    patterns_text = "\n".join(pattern_lines)
    project_name = project_filter or "Project"
    template = AGENT_CONFIG_TEMPLATES.get(format, AGENT_CONFIG_TEMPLATES["claude.md"])
    content = template.format(project_name=project_name, patterns=patterns_text)

    return _json_dumps({
        "format": format,
        "content": content,
        "pattern_count": len(patterns),
    })
