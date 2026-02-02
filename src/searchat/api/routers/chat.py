"""Chat endpoints for RAG answers."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse

from searchat.api.models import ChatRequest, ChatRagRequest, ConversationSource, RAGResponse
from searchat.api.utils import detect_source_from_path, detect_tool_from_path
from searchat.api.dependencies import get_config, trigger_search_engine_warmup
from searchat.api.readiness import get_readiness, warming_payload, error_payload
from searchat.services.chat_service import generate_answer_stream, generate_rag_response
from searchat.services.llm_service import LLMServiceError


router = APIRouter()


@router.post("/chat")
async def chat(
    request: ChatRequest,
    snapshot: str | None = Query(None, description="Backup snapshot name (read-only)"),
):
    if snapshot is not None:
        raise HTTPException(status_code=403, detail="Chat is disabled in snapshot mode")
    provider = request.model_provider.lower()
    if provider not in ("openai", "ollama", "embedded"):
        raise HTTPException(status_code=400, detail="model_provider must be 'openai', 'ollama', or 'embedded'.")

    readiness = get_readiness().snapshot()
    required = ["metadata", "faiss", "embedder"]
    if provider == "embedded":
        required.append("embedded_model")

    for key in required:
        if readiness.components.get(key) == "error":
            return JSONResponse(status_code=500, content=error_payload())

    if any(readiness.components.get(key) != "ready" for key in required):
        trigger_search_engine_warmup()
        return JSONResponse(status_code=503, content=warming_payload())

    config = get_config()
    try:
        stream = generate_answer_stream(
            query=request.query,
            provider=provider,
            model_name=request.model_name,
            config=config,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return StreamingResponse(stream, media_type="text/plain; charset=utf-8")


@router.post("/chat-rag", response_model=RAGResponse)
async def chat_rag(
    request: ChatRagRequest,
    snapshot: str | None = Query(None, description="Backup snapshot name (read-only)"),
):
    if snapshot is not None:
        raise HTTPException(status_code=403, detail="Chat is disabled in snapshot mode")
    provider = request.model_provider.lower()
    if provider not in ("openai", "ollama", "embedded"):
        raise HTTPException(status_code=400, detail="model_provider must be 'openai', 'ollama', or 'embedded'.")

    readiness = get_readiness().snapshot()
    required = ["metadata", "faiss", "embedder"]
    if provider == "embedded":
        required.append("embedded_model")

    for key in required:
        if readiness.components.get(key) == "error":
            return JSONResponse(status_code=500, content=error_payload())

    if any(readiness.components.get(key) != "ready" for key in required):
        trigger_search_engine_warmup()
        return JSONResponse(status_code=503, content=warming_payload())

    config = get_config()
    if not config.chat.enable_rag:
        raise HTTPException(status_code=404, detail="RAG chat endpoint is disabled.")
    try:
        generation = generate_rag_response(
            query=request.query,
            provider=provider,
            model_name=request.model_name,
            config=config,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            system_prompt=request.system_prompt,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    sources: list[ConversationSource]
    if not config.chat.enable_citations:
        sources = []
    else:
        sources = [
            ConversationSource(
                conversation_id=r.conversation_id,
                project_id=r.project_id,
                title=r.title,
                file_path=r.file_path,
                updated_at=r.updated_at.isoformat(),
                score=r.score,
                snippet=r.snippet,
                message_start_index=r.message_start_index,
                message_end_index=r.message_end_index,
                source=detect_source_from_path(r.file_path),
                tool=detect_tool_from_path(r.file_path),
            )
            for r in generation.results
        ]
    return RAGResponse(answer=generation.answer, sources=sources, context_used=generation.context_used)
