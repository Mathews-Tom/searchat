from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


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
