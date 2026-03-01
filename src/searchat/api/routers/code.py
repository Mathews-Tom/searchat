from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from searchat.api.models import CodeSearchResponse
from searchat.api.utils import (
    resolve_dataset,
    ensure_code_index_has_symbol_columns,
    rows_to_code_results,
)
import searchat.api.dependencies as deps


router = APIRouter()


class CodeHighlightBlock(BaseModel):
    code: str
    language: str | None = None
    language_source: Literal["fence", "detected"]


class CodeHighlightRequest(BaseModel):
    blocks: list[CodeHighlightBlock] = Field(min_length=1, max_length=200)


class CodeHighlightResult(BaseModel):
    html: str
    used_language: str
    guessed: bool


class CodeHighlightResponse(BaseModel):
    results: list[CodeHighlightResult]


class CodeSymbolsResponse(BaseModel):
    conversation_id: str
    functions: list[str]
    classes: list[str]
    imports: list[str]


@router.post("/code/highlight", response_model=CodeHighlightResponse)
async def highlight_code(request: CodeHighlightRequest) -> CodeHighlightResponse:
    try:
        from pygments import highlight
        from pygments.formatters import HtmlFormatter
        from pygments.lexers import TextLexer, get_lexer_by_name, guess_lexer
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Pygments is required for code highlighting") from exc

    formatter = HtmlFormatter(nowrap=True)
    results: list[CodeHighlightResult] = []

    for block in request.blocks:
        code = block.code
        if not isinstance(code, str) or not code.strip():
            results.append(CodeHighlightResult(html="", used_language="plaintext", guessed=False))
            continue

        if block.language_source == "fence" and block.language:
            try:
                lexer = get_lexer_by_name(block.language)
                used_language = block.language
            except Exception:
                lexer = TextLexer()
                used_language = "plaintext"
            guessed = False
        else:
            try:
                lexer = guess_lexer(code)
                used_language = getattr(lexer, "name", "") or "guessed"
            except Exception:
                lexer = TextLexer()
                used_language = "plaintext"
            guessed = True

        html = highlight(code, lexer, formatter)
        results.append(CodeHighlightResult(html=html, used_language=used_language, guessed=guessed))

    return CodeHighlightResponse(results=results)


@router.get("/conversation/{conversation_id}/code-symbols", response_model=CodeSymbolsResponse)
async def get_conversation_code_symbols(
    conversation_id: str,
    snapshot: str | None = Query(None, description="Backup snapshot name (read-only)"),
) -> CodeSymbolsResponse:
    """Return aggregated code symbols for a conversation from the code index."""

    try:
        search_dir, _snapshot_name = resolve_dataset(snapshot)

        code_dir = search_dir / "data" / "code"
        if not code_dir.exists() or not any(code_dir.glob("*.parquet")):
            raise HTTPException(
                status_code=503,
                detail="Code index not found. Rebuild the index to enable code symbol endpoints.",
            )

        parquet_glob = str(code_dir / "*.parquet")
        conn = deps.get_duckdb_store_for(search_dir)._connect()
        try:
            ensure_code_index_has_symbol_columns(conn, parquet_glob)

            functions_rows = conn.execute(
                "SELECT DISTINCT unnest(functions) AS v FROM parquet_scan(?) WHERE conversation_id = ?",
                [parquet_glob, conversation_id],
            ).fetchall()
            classes_rows = conn.execute(
                "SELECT DISTINCT unnest(classes) AS v FROM parquet_scan(?) WHERE conversation_id = ?",
                [parquet_glob, conversation_id],
            ).fetchall()
            imports_rows = conn.execute(
                "SELECT DISTINCT unnest(imports) AS v FROM parquet_scan(?) WHERE conversation_id = ?",
                [parquet_glob, conversation_id],
            ).fetchall()
        finally:
            conn.close()

        return CodeSymbolsResponse(
            conversation_id=conversation_id,
            functions=sorted({r[0] for r in functions_rows if r and r[0]}),
            classes=sorted({r[0] for r in classes_rows if r and r[0]}),
            imports=sorted({r[0] for r in imports_rows if r and r[0]}),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/code/functions", response_model=CodeSearchResponse)
async def search_code_functions(
    name: str = Query(..., description="Function name (exact match)", min_length=1),
    language: str | None = Query(None, description="Filter by language (e.g. python)"),
    project: str | None = Query(None, description="Filter by project"),
    tool: str | None = Query(None, description="Filter by tool/connector"),
    limit: int = Query(20, description="Max results per page (1-100)", ge=1, le=100),
    offset: int = Query(0, description="Number of results to skip for pagination", ge=0),
    snapshot: str | None = Query(None, description="Backup snapshot name (read-only)"),
) -> CodeSearchResponse:
    return await _search_code_symbol(
        column="functions",
        value=name,
        language=language,
        project=project,
        tool=tool,
        limit=limit,
        offset=offset,
        snapshot=snapshot,
    )


@router.get("/code/imports", response_model=CodeSearchResponse)
async def search_code_imports(
    module: str = Query(..., description="Import/module name (exact match)", min_length=1),
    language: str | None = Query(None, description="Filter by language (e.g. python)"),
    project: str | None = Query(None, description="Filter by project"),
    tool: str | None = Query(None, description="Filter by tool/connector"),
    limit: int = Query(20, description="Max results per page (1-100)", ge=1, le=100),
    offset: int = Query(0, description="Number of results to skip for pagination", ge=0),
    snapshot: str | None = Query(None, description="Backup snapshot name (read-only)"),
) -> CodeSearchResponse:
    return await _search_code_symbol(
        column="imports",
        value=module,
        language=language,
        project=project,
        tool=tool,
        limit=limit,
        offset=offset,
        snapshot=snapshot,
    )


async def _search_code_symbol(
    *,
    column: str,
    value: str,
    language: str | None,
    project: str | None,
    tool: str | None,
    limit: int,
    offset: int,
    snapshot: str | None,
) -> CodeSearchResponse:
    try:
        search_dir, _snapshot_name = resolve_dataset(snapshot)

        code_dir = search_dir / "data" / "code"
        if not code_dir.exists() or not any(code_dir.glob("*.parquet")):
            raise HTTPException(
                status_code=503,
                detail="Code index not found. Rebuild the index to enable code symbol endpoints.",
            )

        parquet_glob = str(code_dir / "*.parquet")
        conn = deps.get_duckdb_store_for(search_dir)._connect()
        try:
            ensure_code_index_has_symbol_columns(conn, parquet_glob)

            filters: list[str] = [f"list_contains({column}, ?)"]
            params: list[object] = [value]
            if language:
                filters.append("lower(language) = lower(?)")
                params.append(language)
            if project:
                filters.append("project_id = ?")
                params.append(project)
            if tool:
                filters.append("lower(connector) = lower(?)")
                params.append(tool)

            where_sql = "WHERE " + " AND ".join(filters)

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

        return CodeSearchResponse(
            results=results,
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + limit) < total,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
