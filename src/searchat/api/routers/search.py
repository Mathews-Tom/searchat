"""Search endpoints - main search and projects list."""
from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Query, HTTPException

from searchat.api.contracts import serialize_projects_payload, serialize_search_payload
from searchat.models import SearchMode, SearchFilters
from searchat.services.highlight_service import extract_highlight_terms
from searchat.services.llm_service import LLMServiceError
from searchat.api.dataset_access import _DatasetNotReady, get_dataset_retrieval, get_dataset_store
from searchat.api.utils import (
    parse_date_filter,
    validate_tool,
    sort_results,
    ensure_code_index_has_symbol_columns,
    rows_to_code_results,
)
import searchat.api.dependencies as deps
from searchat.api import state as api_state

from searchat.api.dependencies import get_analytics_service


router = APIRouter()


@lru_cache(maxsize=128)
def _cached_highlight(
    dataset_key: str, query: str, provider: str, model: str | None,
) -> list[str]:
    """LRU-cached highlight term extraction."""
    config = deps.get_config()
    return extract_highlight_terms(
        query=query, provider=provider, model_name=model, config=config,
    )


def _resolve_highlight_terms(
    dataset_key: str, query: str, provider: str, model: str | None,
) -> list[str] | None:
    """Treat highlight extraction as optional enrichment, not a search prerequisite."""
    try:
        return _cached_highlight(dataset_key, query, provider, model)
    except (LLMServiceError, ValueError):
        return None


@router.get("/search/code")
async def search_code(
    q: str = Query("*", description="Code search query (use * to list recent)"),
    language: str | None = Query(None, description="Filter by language (e.g. python)"),
    function: str | None = Query(None, description="Filter by function name (exact match)"),
    class_name: str | None = Query(None, description="Filter by class name (exact match)"),
    import_name: str | None = Query(None, description="Filter by import/module name (exact match)"),
    project: str | None = Query(None, description="Filter by project"),
    tool: str | None = Query(
        None,
        description="Filter by tool: claude, vibe, opencode, codex, gemini, continue, cursor, aider",
    ),
    limit: int = Query(20, description="Max results per page (1-100)", ge=1, le=100),
    offset: int = Query(0, description="Number of results to skip for pagination", ge=0),
    snapshot: str | None = Query(None, description="Backup snapshot name (read-only)"),
):
    """Search fenced code blocks extracted during indexing."""
    try:
        dataset = get_dataset_store(snapshot)
        search_dir = dataset.search_dir

        code_dir = search_dir / "data" / "code"
        if not code_dir.exists() or not any(code_dir.glob("*.parquet")):
            raise HTTPException(
                status_code=503,
                detail="Code index not found. Rebuild the index to enable /api/search/code.",
            )

        filters: list[str] = []
        params: list[object] = []

        if q.strip() != "*":
            terms = [t for t in q.strip().split() if t]
            if not terms:
                terms = [q.strip()]
            for term in terms:
                filters.append("code ILIKE '%' || ? || '%' ")
                params.append(term)

        if language:
            filters.append("lower(language) = lower(?)")
            params.append(language)
        if project:
            filters.append("project_id = ?")
            params.append(project)
        if tool:
            filters.append("lower(connector) = lower(?)")
            params.append(validate_tool(tool))

        parquet_glob = str(code_dir / "*.parquet")
        conn = dataset.store._connect()
        try:
            if function or class_name or import_name:
                ensure_code_index_has_symbol_columns(conn, parquet_glob)

            if function:
                filters.append("list_contains(functions, ?)")
                params.append(function)
            if class_name:
                filters.append("list_contains(classes, ?)")
                params.append(class_name)
            if import_name:
                filters.append("list_contains(imports, ?)")
                params.append(import_name)

            where_sql = "WHERE " + " AND ".join(filters) if filters else ""

            query_sql = f"""
                SELECT
                    conversation_id, project_id, title, file_path, connector,
                    message_index, block_index, role, language, language_source,
                    fence_language, lines, code, code_hash,
                    conversation_updated_at, count(*) OVER() AS total_count
                FROM parquet_scan(?)
                {where_sql}
                ORDER BY conversation_updated_at DESC, message_timestamp DESC
                LIMIT ? OFFSET ?
            """

            rows = conn.execute(query_sql, [parquet_glob, *params, limit, offset]).fetchall()
        finally:
            conn.close()

        total, results = rows_to_code_results(rows)

        return {
            "results": results,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/search")
async def search(
    q: str = Query(..., description="Search query"),
    mode: str = Query("hybrid", description="Search mode: hybrid, semantic, or keyword"),
    project: str | None = Query(None, description="Filter by project"),
    date: str | None = Query(None, description="Date filter: today, week, month, or custom"),
    date_from: str | None = Query(None, description="Custom date from (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="Custom date to (YYYY-MM-DD)"),
    tool: str | None = Query(None, description="Filter by tool: claude, vibe, opencode, codex, gemini, continue, cursor, aider"),
    sort_by: str = Query("relevance", description="Sort by: relevance, date_newest, date_oldest, messages"),
    limit: int = Query(20, description="Max results per page (1-100)", ge=1, le=100),
    offset: int = Query(0, description="Number of results to skip for pagination", ge=0),
    highlight: bool = Query(False, description="Enable semantic highlight term extraction"),
    highlight_provider: str | None = Query(None, description="LLM provider for highlights (openai, ollama)"),
    highlight_model: str | None = Query(None, description="LLM model override for highlights"),
    snapshot: str | None = Query(None, description="Backup snapshot name (read-only)"),
):
    """Search conversations with filters and sorting."""
    try:
        # Convert mode string to SearchMode enum
        mode_map = {
            "hybrid": SearchMode.HYBRID,
            "semantic": SearchMode.SEMANTIC,
            "keyword": SearchMode.KEYWORD,
        }
        if mode not in mode_map:
            raise HTTPException(status_code=400, detail="Invalid search mode")
        search_mode = mode_map[mode]

        if q.strip() == "*":
            search_mode = SearchMode.KEYWORD

        try:
            dataset = get_dataset_retrieval(snapshot, search_mode=search_mode)
        except _DatasetNotReady as exc:
            return exc.response

        search_dir = dataset.search_dir
        snapshot_name = dataset.snapshot_name
        search_engine = dataset.retrieval_service

        # Build filters
        filters = SearchFilters()
        if project:
            filters.project_ids = [project]
        if tool:
            filters.tool = validate_tool(tool)
        filters.date_from, filters.date_to = parse_date_filter(date, date_from, date_to)

        results = search_engine.search(q, mode=search_mode, filters=filters)

        highlight_terms = None
        if highlight and len(q.strip()) >= 4 and mode != "keyword":
            if highlight_provider is None:
                raise HTTPException(status_code=400, detail="Highlight provider is required")
            provider = highlight_provider.lower()
            if provider not in ("openai", "ollama"):
                raise HTTPException(status_code=400, detail="Invalid highlight provider")
            highlight_terms = _resolve_highlight_terms(
                str(search_dir), q, provider, highlight_model
            )

        # Log search analytics (opt-in; active dataset only)
        config = deps.get_config()
        if snapshot_name is None and config.analytics.enabled:
            try:
                analytics = get_analytics_service()
                analytics.log_search(
                    query=q,
                    result_count=len(results.results),
                    search_mode=mode,
                    search_time_ms=int(results.search_time_ms),
                    tool_filter=tool,
                )
            except Exception:
                pass

        sorted_results = sort_results(results.results, sort_by)
        total_results = len(sorted_results)
        paginated_results = sorted_results[offset:offset + limit]

        return serialize_search_payload(
            results=paginated_results,
            total=total_results,
            search_time_ms=results.search_time_ms,
            limit=limit,
            offset=offset,
            highlight_terms=highlight_terms,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects")
async def get_projects(snapshot: str | None = Query(None, description="Backup snapshot name (read-only)")):
    """Get list of all projects in the index."""
    dataset = get_dataset_store(snapshot)
    snapshot_name = dataset.snapshot_name
    store = dataset.store

    if snapshot_name is not None:
        return serialize_projects_payload(store.list_projects())

    if api_state.projects_cache is None:
        api_state.projects_cache = serialize_projects_payload(store.list_projects())
    return api_state.projects_cache


@router.get("/projects/summary")
async def get_projects_summary(snapshot: str | None = Query(None, description="Backup snapshot name (read-only)")):
    """Get summary stats for all projects in the index."""
    dataset = get_dataset_store(snapshot)
    snapshot_name = dataset.snapshot_name
    store = dataset.store

    if snapshot_name is not None:
        return store.list_project_summaries()

    if api_state.projects_summary_cache is None:
        api_state.projects_summary_cache = store.list_project_summaries()
    return api_state.projects_summary_cache


@router.get("/search/suggestions")
async def get_search_suggestions(
    q: str = Query(..., description="Prefix to search for", min_length=1),
    limit: int = Query(10, description="Max suggestions to return (1-20)", ge=1, le=20)
):
    """Get search suggestions based on conversation titles and common terms."""
    try:
        store = deps.get_duckdb_store()

        # Get all conversation titles and extract terms
        query = """
            SELECT DISTINCT title
            FROM conversations
            WHERE title IS NOT NULL
            ORDER BY updated_at DESC
            LIMIT 1000
        """

        conn = store._connect()
        result = conn.execute(query).fetchall()

        suggestions = set()
        q_lower = q.lower()

        # Extract words and phrases from titles
        for (title,) in result:
            if not title:
                continue

            title_lower = title.lower()

            # Add full title if it matches
            if q_lower in title_lower:
                suggestions.add(title)

            # Extract individual words
            words = title.split()
            for word in words:
                # Clean word (remove punctuation)
                clean_word = ''.join(c for c in word if c.isalnum() or c in ['-', '_'])
                if len(clean_word) >= 3 and clean_word.lower().startswith(q_lower):
                    suggestions.add(clean_word)

            # Extract common phrases (2-3 words)
            for i in range(len(words) - 1):
                # 2-word phrase
                phrase = ' '.join(words[i:i+2])
                if phrase.lower().startswith(q_lower) or q_lower in phrase.lower():
                    suggestions.add(phrase)

                # 3-word phrase
                if i < len(words) - 2:
                    phrase = ' '.join(words[i:i+3])
                    if phrase.lower().startswith(q_lower) or q_lower in phrase.lower():
                        suggestions.add(phrase)

        # Sort suggestions by relevance (prefix match first, then contains)
        sorted_suggestions = sorted(
            suggestions,
            key=lambda s: (
                not s.lower().startswith(q_lower),  # Prefix matches first
                len(s),  # Shorter suggestions first
                s.lower()  # Alphabetical
            )
        )

        return {
            "query": q,
            "suggestions": sorted_suggestions[:limit]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
