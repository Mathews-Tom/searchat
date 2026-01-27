"""Chat endpoints for RAG answers."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from searchat.api.models import ChatRequest
from searchat.api.dependencies import get_config, trigger_search_engine_warmup
from searchat.api.readiness import get_readiness, warming_payload, error_payload
from searchat.services.chat_service import generate_answer_stream
from searchat.services.llm_service import LLMServiceError


router = APIRouter()


@router.post("/chat")
async def chat(request: ChatRequest):
    provider = request.model_provider.lower()
    if provider not in ("openai", "ollama"):
        raise HTTPException(status_code=400, detail="model_provider must be 'openai' or 'ollama'.")

    readiness = get_readiness().snapshot()
    for key in ("metadata", "faiss", "embedder"):
        if readiness.components.get(key) == "error":
            return JSONResponse(status_code=500, content=error_payload())

    if any(readiness.components.get(key) != "ready" for key in ("metadata", "faiss", "embedder")):
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
