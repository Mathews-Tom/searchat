"""Search endpoints - main search and projects list."""
from __future__ import annotations

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse

from searchat.config.constants import VALID_TOOL_NAMES
from searchat.models import SearchMode, SearchFilters
from searchat.api.models import SearchResultResponse, CodeSearchResultResponse
from searchat.services.highlight_service import extract_highlight_terms
from searchat.services.llm_service import LLMServiceError
from searchat.api.utils import detect_tool_from_path, detect_source_from_path, parse_date_filter
import searchat.api.dependencies as deps

from searchat.api.dependencies import get_analytics_service
from searchat.api.readiness import get_readiness, warming_payload, error_payload


router = APIRouter()
_highlight_cache: dict[tuple[str, str, str, str | None], list[str]] = {}


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
        try:
            search_dir, _snapshot_name = deps.resolve_dataset_search_dir(snapshot)
        except ValueError as exc:
            msg = str(exc)
            if msg == "Snapshot not found":
                raise HTTPException(status_code=404, detail="Snapshot not found") from exc
            raise HTTPException(status_code=400, detail=msg) from exc

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
            tool_value = tool.lower()
            if tool_value not in VALID_TOOL_NAMES:
                raise HTTPException(status_code=400, detail="Invalid tool filter")
            filters.append("lower(connector) = lower(?)")
            params.append(tool_value)

        where_sql = ""
        if filters:
            where_sql = "WHERE " + " AND ".join(filters)

        query_sql = f"""
            SELECT
                conversation_id,
                project_id,
                title,
                file_path,
                connector,
                message_index,
                block_index,
                role,
                language,
                language_source,
                fence_language,
                lines,
                code,
                code_hash,
                conversation_updated_at,
                count(*) OVER() AS total_count
            FROM parquet_scan(?)
            {where_sql}
            ORDER BY conversation_updated_at DESC, message_timestamp DESC
            LIMIT ? OFFSET ?
        """

        parquet_glob = str(code_dir / "*.parquet")
        conn = deps.get_duckdb_store_for(search_dir)._connect()
        try:
            if function or class_name or import_name:
                _ensure_code_index_has_symbol_columns(conn, parquet_glob)

            if function:
                filters.append("list_contains(functions, ?)")
                params.append(function)
            if class_name:
                filters.append("list_contains(classes, ?)")
                params.append(class_name)
            if import_name:
                filters.append("list_contains(imports, ?)")
                params.append(import_name)

            where_sql = ""
            if filters:
                where_sql = "WHERE " + " AND ".join(filters)

            query_sql = f"""
                SELECT
                    conversation_id,
                    project_id,
                    title,
                    file_path,
                    connector,
                    message_index,
                    block_index,
                    role,
                    language,
                    language_source,
                    fence_language,
                    lines,
                    code,
                    code_hash,
                    conversation_updated_at,
                    count(*) OVER() AS total_count
                FROM parquet_scan(?)
                {where_sql}
                ORDER BY conversation_updated_at DESC, message_timestamp DESC
                LIMIT ? OFFSET ?
            """

            rows = conn.execute(query_sql, [parquet_glob, *params, limit, offset]).fetchall()
        finally:
            conn.close()

        total = int(rows[0][-1]) if rows else 0
        results: list[CodeSearchResultResponse] = []
        for (
            conversation_id,
            project_id,
            title,
            file_path,
            connector,
            message_index,
            block_index,
            role,
            language_value,
            language_source,
            fence_language,
            lines,
            code,
            code_hash,
            conversation_updated_at,
            _total_count,
        ) in rows:
            code_text = code or ""
            # Hard cap to avoid huge payloads.
            max_chars = 4000
            if len(code_text) > max_chars:
                code_text = code_text[:max_chars]

            updated_at_str = (
                conversation_updated_at
                if isinstance(conversation_updated_at, str)
                else conversation_updated_at.isoformat()
            )
            results.append(
                CodeSearchResultResponse(
                    conversation_id=conversation_id,
                    project_id=project_id,
                    title=title,
                    file_path=file_path,
                    tool=connector,
                    message_index=int(message_index),
                    block_index=int(block_index),
                    role=role,
                    language=language_value,
                    language_source=language_source,
                    fence_language=fence_language,
                    lines=int(lines),
                    code=code_text,
                    code_hash=code_hash,
                    conversation_updated_at=updated_at_str,
                )
            )

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


def _ensure_code_index_has_symbol_columns(conn, parquet_glob: str) -> None:
    """Fail fast if the code index doesn't include symbol metadata columns."""
    try:
        cursor = conn.execute("SELECT * FROM parquet_scan(?) LIMIT 0", [parquet_glob])
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Failed to read code index schema: {exc}") from exc

    columns: set[str] = set()
    for desc in getattr(cursor, "description", []) or []:
        if desc and isinstance(desc[0], str):
            columns.add(desc[0])

    required = {"functions", "classes", "imports"}
    if not required.issubset(columns):
        raise HTTPException(
            status_code=503,
            detail="Code index does not include symbol metadata. Rebuild the index to enable symbol filters.",
        )


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
        try:
            search_dir, snapshot_name = deps.resolve_dataset_search_dir(snapshot)
        except ValueError as exc:
            msg = str(exc)
            if msg == "Snapshot not found":
                raise HTTPException(status_code=404, detail="Snapshot not found") from exc
            raise HTTPException(status_code=400, detail=msg) from exc

        # Convert mode string to SearchMode enum
        mode_map = {
            "hybrid": SearchMode.HYBRID,
            "semantic": SearchMode.SEMANTIC,
            "keyword": SearchMode.KEYWORD
        }
        if mode not in mode_map:
            raise HTTPException(status_code=400, detail="Invalid search mode")
        search_mode = mode_map[mode]

        # Treat wildcard as keyword-only browsing.
        if q.strip() == "*":
            search_mode = SearchMode.KEYWORD

        # Snapshot requests must not mutate readiness/warmup globals.
        if snapshot_name is not None:
            search_engine = deps.get_or_create_search_engine_for(search_dir)
        else:
            # Keyword search should work without semantic warmup.
            if search_mode == SearchMode.KEYWORD:
                search_engine = deps.get_or_create_search_engine()
            else:
                readiness = get_readiness().snapshot()
                for key in ("metadata", "faiss", "embedder"):
                    if readiness.components.get(key) == "error":
                        return JSONResponse(status_code=500, content=error_payload())
                if any(readiness.components.get(key) != "ready" for key in ("metadata", "faiss", "embedder")):
                    deps.trigger_search_engine_warmup()
                    return JSONResponse(status_code=503, content=warming_payload())

                search_engine = deps.get_search_engine()

        # Build filters
        filters = SearchFilters()
        if project:
            filters.project_ids = [project]

        if tool:
            tool_value = tool.lower()
            if tool_value not in VALID_TOOL_NAMES:
                raise HTTPException(status_code=400, detail="Invalid tool filter")
            filters.tool = tool_value

        # Handle date filtering
        filters.date_from, filters.date_to = parse_date_filter(date, date_from, date_to)

        # Execute search
        results = search_engine.search(q, mode=search_mode, filters=filters)

        highlight_terms = None
        if highlight and len(q.strip()) >= 4 and mode != "keyword":
            config = deps.get_config()
            if highlight_provider is None:
                raise HTTPException(status_code=400, detail="Highlight provider is required")
            provider = highlight_provider.lower()
            if provider not in ("openai", "ollama"):
                raise HTTPException(status_code=400, detail="Invalid highlight provider")

            dataset_cache_key = str(search_dir)
            cache_key = (dataset_cache_key, q, provider, highlight_model)
            if cache_key in _highlight_cache:
                highlight_terms = _highlight_cache[cache_key]
            else:
                try:
                    highlight_terms = extract_highlight_terms(
                        query=q,
                        provider=provider,
                        model_name=highlight_model,
                        config=config,
                    )
                except LLMServiceError as exc:
                    raise HTTPException(status_code=503, detail=str(exc)) from exc
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc

                _highlight_cache[cache_key] = highlight_terms

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
                # Don't fail the search if analytics logging fails
                pass

        # Sort results based on sort_by parameter
        sorted_results = results.results.copy()
        if sort_by == "date_newest":
            sorted_results.sort(key=lambda r: r.updated_at, reverse=True)
        elif sort_by == "date_oldest":
            sorted_results.sort(key=lambda r: r.updated_at, reverse=False)
        elif sort_by == "messages":
            sorted_results.sort(key=lambda r: r.message_count, reverse=True)
        # else keep default relevance sorting (by score)

        # Apply pagination
        total_results = len(sorted_results)
        paginated_results = sorted_results[offset:offset + limit]

        # Convert results to response format
        response_results = []
        for r in paginated_results:
            response_results.append(SearchResultResponse(
                conversation_id=r.conversation_id,
                project_id=r.project_id,
                title=r.title,
                created_at=r.created_at.isoformat(),
                updated_at=r.updated_at.isoformat(),
                message_count=r.message_count,
                file_path=r.file_path,
                snippet=r.snippet,
                score=r.score,
                message_start_index=r.message_start_index,
                message_end_index=r.message_end_index,
                source=detect_source_from_path(r.file_path),
                tool=detect_tool_from_path(r.file_path),
            ))

        return {
            "results": response_results,
            "total": total_results,
            "search_time_ms": results.search_time_ms,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total_results,
            "highlight_terms": highlight_terms,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects")
async def get_projects(snapshot: str | None = Query(None, description="Backup snapshot name (read-only)")):
    """Get list of all projects in the index."""
    try:
        search_dir, snapshot_name = deps.resolve_dataset_search_dir(snapshot)
    except ValueError as exc:
        msg = str(exc)
        if msg == "Snapshot not found":
            raise HTTPException(status_code=404, detail="Snapshot not found") from exc
        raise HTTPException(status_code=400, detail=msg) from exc
    store = deps.get_duckdb_store_for(search_dir)

    if snapshot_name is not None:
        return store.list_projects()

    if deps.projects_cache is None:
        deps.projects_cache = store.list_projects()
    return deps.projects_cache


@router.get("/projects/summary")
async def get_projects_summary(snapshot: str | None = Query(None, description="Backup snapshot name (read-only)")):
    """Get summary stats for all projects in the index."""
    try:
        search_dir, snapshot_name = deps.resolve_dataset_search_dir(snapshot)
    except ValueError as exc:
        msg = str(exc)
        if msg == "Snapshot not found":
            raise HTTPException(status_code=404, detail="Snapshot not found") from exc
        raise HTTPException(status_code=400, detail=msg) from exc
    store = deps.get_duckdb_store_for(search_dir)

    if snapshot_name is not None:
        return store.list_project_summaries()

    if deps.projects_summary_cache is None:
        deps.projects_summary_cache = store.list_project_summaries()
    return deps.projects_summary_cache


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
