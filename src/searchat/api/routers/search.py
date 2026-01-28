"""Search endpoints - main search and projects list."""
from __future__ import annotations

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse

from searchat.models import SearchMode, SearchFilters
from searchat.api.models import SearchResultResponse
from searchat.api.utils import detect_tool_from_path, detect_source_from_path, parse_date_filter
import searchat.api.dependencies as deps

from searchat.api.dependencies import (
    get_search_engine,
    get_or_create_search_engine,
    trigger_search_engine_warmup,
    get_analytics_service
)
from searchat.api.readiness import get_readiness, warming_payload, error_payload


router = APIRouter()


@router.get("/search")
async def search(
    q: str = Query(..., description="Search query"),
    mode: str = Query("hybrid", description="Search mode: hybrid, semantic, or keyword"),
    project: str | None = Query(None, description="Filter by project"),
    date: str | None = Query(None, description="Date filter: today, week, month, or custom"),
    date_from: str | None = Query(None, description="Custom date from (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="Custom date to (YYYY-MM-DD)"),
    tool: str | None = Query(None, description="Filter by tool: claude, vibe, opencode"),
    sort_by: str = Query("relevance", description="Sort by: relevance, date_newest, date_oldest, messages"),
    limit: int = Query(20, description="Max results per page (1-100)", ge=1, le=100),
    offset: int = Query(0, description="Number of results to skip for pagination", ge=0)
):
    """Search conversations with filters and sorting."""
    try:
        # Convert mode string to SearchMode enum
        mode_map = {
            "hybrid": SearchMode.HYBRID,
            "semantic": SearchMode.SEMANTIC,
            "keyword": SearchMode.KEYWORD
        }
        search_mode = mode_map.get(mode, SearchMode.HYBRID)

        # Treat wildcard as keyword-only browsing.
        if q.strip() == "*":
            search_mode = SearchMode.KEYWORD

        # Keyword search should work without semantic warmup.
        if search_mode == SearchMode.KEYWORD:
            search_engine = get_or_create_search_engine()
        else:
            readiness = get_readiness().snapshot()
            for key in ("metadata", "faiss", "embedder"):
                if readiness.components.get(key) == "error":
                    return JSONResponse(status_code=500, content=error_payload())
            if any(readiness.components.get(key) != "ready" for key in ("metadata", "faiss", "embedder")):
                trigger_search_engine_warmup()
                return JSONResponse(status_code=503, content=warming_payload())

            search_engine = get_search_engine()

        # Build filters
        filters = SearchFilters()
        if project:
            filters.project_ids = [project]

        if tool:
            tool_value = tool.lower()
            if tool_value not in ("claude", "vibe", "opencode"):
                raise HTTPException(status_code=400, detail="Invalid tool filter")
            filters.tool = tool_value

        # Handle date filtering
        filters.date_from, filters.date_to = parse_date_filter(date, date_from, date_to)

        # Execute search
        results = search_engine.search(q, mode=search_mode, filters=filters)

        # Log search analytics
        try:
            analytics = get_analytics_service()
            analytics.log_search(
                query=q,
                result_count=len(results.results),
                search_mode=mode,
                search_time_ms=int(results.search_time_ms)
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
            "has_more": (offset + limit) < total_results
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects")
async def get_projects():
    """Get list of all projects in the index."""
    store = deps.get_duckdb_store()

    if deps.projects_cache is None:
        deps.projects_cache = store.list_projects()
    return deps.projects_cache


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
