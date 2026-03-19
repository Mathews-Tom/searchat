from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from searchat.config import Config, PathResolver
from searchat.config.constants import VALID_TOOL_NAMES, RAG_SYSTEM_PROMPT
from searchat.contracts.errors import (
    conversation_not_found_message,
    invalid_model_provider_message,
    invalid_mcp_mode_message,
    invalid_mcp_tool_message,
    mcp_offset_message,
    mcp_search_limit_message,
    mcp_similarity_limit_message,
    no_embeddings_for_conversation_message,
)
from searchat.mcp.contracts import (
    serialize_conversation_payload,
    serialize_history_answer_payload,
    serialize_projects_payload,
    serialize_search_payload,
    serialize_similar_conversation,
    serialize_similar_conversations_payload,
    serialize_statistics_payload,
)
from searchat.models import SearchFilters, SearchMode
from searchat.services.llm_service import (
    LLMServiceError,
    build_generation_service,
    build_grounded_fallback_answer,
    resolve_generation_target,
)
from searchat.services.retrieval_service import SemanticRetrievalService, build_retrieval_service
from searchat.services.storage_service import StorageService, build_storage_service


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


def build_services(search_dir: Path) -> tuple[Config, SemanticRetrievalService, StorageService]:
    config = Config.load()
    engine = build_retrieval_service(search_dir, config=config)
    store = build_storage_service(search_dir, config=config)
    return config, engine, store


def parse_mode(mode: str) -> SearchMode:
    value = (mode or "").lower().strip()
    if value == "hybrid":
        return SearchMode.HYBRID
    if value == "semantic":
        return SearchMode.SEMANTIC
    if value == "keyword":
        return SearchMode.KEYWORD
    raise ValueError(invalid_mcp_mode_message())


def parse_tool(tool: str | None) -> str | None:
    if tool is None:
        return None
    value = tool.lower().strip()
    if not value:
        return None
    if value not in VALID_TOOL_NAMES:
        raise ValueError(invalid_mcp_tool_message())
    return value


def parse_generation_provider(provider: str | None) -> str | None:
    if provider is None:
        return None
    value = provider.lower().strip()
    if not value:
        return None
    if value not in {"openai", "ollama", "embedded"}:
        raise ValueError(invalid_model_provider_message())
    return value


def ensure_semantic_capability(engine: SemanticRetrievalService) -> None:
    describe = getattr(engine, "describe_capabilities", None)
    if not callable(describe):
        return
    capabilities = describe()
    if capabilities.semantic_available:
        return
    raise RuntimeError(capabilities.semantic_reason or "Semantic search unavailable")


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
        raise ValueError(mcp_search_limit_message())
    if offset < 0:
        raise ValueError(mcp_offset_message())

    mode_value = parse_mode(mode)
    if query.strip() == "*":
        mode_value = SearchMode.KEYWORD
    tool_value = parse_tool(tool)

    dataset_dir = resolve_dataset(search_dir)
    _config, engine, _store = build_services(dataset_dir)
    if mode_value != SearchMode.KEYWORD:
        ensure_semantic_capability(engine)

    filters = SearchFilters()
    if project_id:
        filters.project_ids = [project_id]

    if tool_value is not None:
        filters.tool = tool_value

    results = engine.search(query, mode=mode_value, filters=filters)
    payload = serialize_search_payload(results, limit=limit, offset=offset)
    return _json_dumps(payload)


def get_conversation(*, conversation_id: str, search_dir: str | None = None) -> str:
    dataset_dir = resolve_dataset(search_dir)
    _config, _engine, store = build_services(dataset_dir)

    record = store.get_conversation_record(conversation_id)
    if record is None:
        raise ValueError(conversation_not_found_message(conversation_id))

    return _json_dumps(serialize_conversation_payload(record))


def list_projects(*, search_dir: str | None = None) -> str:
    dataset_dir = resolve_dataset(search_dir)
    _config, _engine, store = build_services(dataset_dir)
    return _json_dumps(serialize_projects_payload(store.list_projects()))


def get_statistics(*, search_dir: str | None = None) -> str:
    dataset_dir = resolve_dataset(search_dir)
    _config, _engine, store = build_services(dataset_dir)
    stats = store.get_statistics()
    return _json_dumps(serialize_statistics_payload(stats))


def find_similar_conversations(
    *,
    conversation_id: str,
    limit: int = 5,
    search_dir: str | None = None,
) -> str:
    if limit < 1 or limit > 20:
        raise ValueError(mcp_similarity_limit_message())

    dataset_dir = resolve_dataset(search_dir)
    _config, engine, store = build_services(dataset_dir)
    ensure_semantic_capability(engine)

    conv_meta = store.get_conversation_meta(conversation_id)
    if not conv_meta:
        raise ValueError(conversation_not_found_message(conversation_id))

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
        raise ValueError(no_embeddings_for_conversation_message())

    chunk_text = row[0]
    representative_text = f"{conv_meta['title']} {chunk_text}"
    hits = [
        (hit.vector_id, hit.distance)
        for hit in engine.find_similar_vector_hits(representative_text, limit + 10)
    ]

    if not hits:
        return _json_dumps(
            serialize_similar_conversations_payload(
                conversation_id=conversation_id,
                title=conv_meta.get("title"),
                similar_conversations=[],
            )
        )

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
                SELECT conversation_id, project_id, title, created_at,
                       updated_at, message_count, file_path
                FROM parquet_scan(?)
                QUALIFY row_number() OVER (
                    PARTITION BY conversation_id ORDER BY updated_at DESC NULLS LAST
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
        similar.append(
            serialize_similar_conversation(
                conversation_id=sim_id,
                project_id=project_id,
                title=title,
                created_at=created_at,
                updated_at=updated_at,
                message_count=message_count,
                file_path=file_path,
                distance=distance,
            )
        )

    return _json_dumps(
        serialize_similar_conversations_payload(
            conversation_id=conversation_id,
            title=conv_meta.get("title"),
            similar_conversations=similar,
        )
    )


def ask_about_history(
    *,
    question: str,
    include_sources: bool = True,
    model_provider: str | None = None,
    model_name: str | None = None,
    search_dir: str | None = None,
) -> str:
    provider_value = parse_generation_provider(model_provider)
    dataset_dir = resolve_dataset(search_dir)
    config, engine, _store = build_services(dataset_dir)
    ensure_semantic_capability(engine)

    target = resolve_generation_target(
        config.llm,
        provider=provider_value,
        model_name=model_name,
    )

    results = engine.search(question, mode=SearchMode.HYBRID, filters=SearchFilters())
    top_results = results.results[:8]
    if not top_results:
        return _json_dumps(
            serialize_history_answer_payload(
                answer="I cannot find the information in the archives.",
                sources=[] if include_sources else None,
            )
        )

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

    llm = build_generation_service(config.llm)
    try:
        answer = llm.completion(
            messages=messages,
            provider=target.provider,
            model_name=target.model_name,
        )
    except LLMServiceError:
        answer = build_grounded_fallback_answer(top_results)

    return _json_dumps(
        serialize_history_answer_payload(
            answer=answer,
            sources=top_results if include_sources else None,
        )
    )


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

    provider_value = parse_generation_provider(model_provider)
    dataset_dir = resolve_dataset(search_dir)
    config, engine, _store = build_services(dataset_dir)
    ensure_semantic_capability(engine)

    target = resolve_generation_target(
        config.llm,
        provider=provider_value,
        model_name=model_name,
    )

    patterns = _extract_patterns(
        topic=topic,
        max_patterns=max_patterns,
        model_provider=target.provider,
        model_name=target.model_name,
        config=config,
        retrieval_service=engine,
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


def prime_expertise(
    *,
    project: str | None = None,
    domain: str | None = None,
    max_tokens: int = 4000,
    search_dir: str | None = None,
) -> str:
    """Return priority-ranked expertise as JSON for agent priming.

    Fetches active expertise records filtered by project/domain, runs priority
    ranking within the given token budget, and returns structured JSON.
    """
    from searchat.expertise.models import ExpertiseQuery
    from searchat.expertise.primer import ExpertisePrioritizer, PrimeFormatter
    from searchat.expertise.store import ExpertiseStore

    if max_tokens < 100 or max_tokens > 32000:
        raise ValueError("max_tokens must be between 100 and 32000")

    dataset_dir = resolve_dataset(search_dir)
    config = Config.load()
    store = ExpertiseStore(dataset_dir)

    q = ExpertiseQuery(
        domain=domain,
        project=project,
        active_only=True,
        limit=100_000,
    )
    records = store.query(q)

    prioritizer = ExpertisePrioritizer()
    result = prioritizer.prioritize(records, max_tokens=max_tokens)

    formatter = PrimeFormatter()
    payload = formatter.format_json(
        result,
        contradiction_ids=getattr(prioritizer, "_contradiction_ids", None),
        qualifying_notes=getattr(prioritizer, "_qualifying_notes", None),
    )
    return _json_dumps(payload)


def record_expertise(
    *,
    type: str,
    domain: str,
    content: str,
    project: str | None = None,
    severity: str | None = None,
    resolution: str | None = None,
    rationale: str | None = None,
    search_dir: str | None = None,
) -> str:
    """Record a new expertise item in the knowledge store.

    Returns JSON with the created record's ID and action taken.
    """
    from searchat.expertise.models import ExpertiseRecord, ExpertiseSeverity, ExpertiseType
    from searchat.expertise.store import ExpertiseStore

    try:
        record_type = ExpertiseType(type)
    except ValueError:
        raise ValueError(f"Invalid type: {type!r}. Valid: {[t.value for t in ExpertiseType]}")

    severity_val = None
    if severity is not None:
        try:
            severity_val = ExpertiseSeverity(severity)
        except ValueError:
            raise ValueError(
                f"Invalid severity: {severity!r}. Valid: {[s.value for s in ExpertiseSeverity]}"
            )

    record = ExpertiseRecord(
        type=record_type,
        domain=domain,
        content=content,
        project=project,
        severity=severity_val,
        resolution=resolution,
        rationale=rationale,
    )

    dataset_dir = resolve_dataset(search_dir)
    store = ExpertiseStore(dataset_dir)
    record_id = store.insert(record)

    return _json_dumps({
        "id": record_id,
        "action": "created",
        "type": record_type.value,
        "domain": domain,
        "content": content,
        "project": project,
        "severity": severity_val.value if severity_val else None,
        "created_at": record.created_at,
    })


def search_expertise(
    *,
    query: str,
    domain: str | None = None,
    type: str | None = None,
    limit: int = 5,
    search_dir: str | None = None,
) -> str:
    """Search expertise records by text query.

    Returns JSON with matching active expertise records.
    """
    from searchat.expertise.models import ExpertiseQuery, ExpertiseType
    from searchat.expertise.store import ExpertiseStore

    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")

    type_filter = None
    if type is not None:
        try:
            type_filter = ExpertiseType(type)
        except ValueError:
            raise ValueError(f"Invalid type: {type!r}. Valid: {[t.value for t in ExpertiseType]}")

    dataset_dir = resolve_dataset(search_dir)
    store = ExpertiseStore(dataset_dir)

    q = ExpertiseQuery(
        q=query,
        domain=domain,
        type=type_filter,
        active_only=True,
        limit=limit,
    )
    records = store.query(q)

    return _json_dumps({
        "results": [
            {
                "id": r.id,
                "type": r.type.value,
                "domain": r.domain,
                "content": r.content,
                "project": r.project,
                "confidence": r.confidence,
                "severity": r.severity.value if r.severity else None,
                "tags": r.tags,
                "source_conversation_id": r.source_conversation_id,
                "source_agent": r.source_agent,
                "name": r.name,
                "rationale": r.rationale,
                "resolution": r.resolution,
                "created_at": r.created_at,
                "last_validated": r.last_validated,
                "validation_count": r.validation_count,
                "is_active": r.is_active,
            }
            for r in records
        ],
        "total": len(records),
        "query": query,
        "domain": domain,
        "type": type,
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

    provider_value = parse_generation_provider(model_provider)
    dataset_dir = resolve_dataset(search_dir)
    config, engine, _store = build_services(dataset_dir)
    ensure_semantic_capability(engine)

    target = resolve_generation_target(
        config.llm,
        provider=provider_value,
        model_name=model_name,
    )

    patterns = _extract_patterns(
        topic=project_filter,
        max_patterns=15,
        model_provider=target.provider,
        model_name=target.model_name,
        config=config,
        retrieval_service=engine,
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
