"""Saved queries endpoints for managing reusable searches."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import searchat.api.dependencies as deps


router = APIRouter()


class SavedQueryCreateRequest(BaseModel):
    name: str
    description: str | None = None
    query: str
    filters: dict[str, Any]
    mode: str


class SavedQueryUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    query: str | None = None
    filters: dict[str, Any] | None = None
    mode: str | None = None


@router.get("/queries")
async def list_saved_queries():
    try:
        service = deps.get_saved_queries_service()
        return {
            "total": len(service.list_queries()),
            "queries": service.list_queries(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/queries")
async def create_saved_query(request: SavedQueryCreateRequest):
    try:
        service = deps.get_saved_queries_service()
        query = service.create_query(request.model_dump())
        return {"success": True, "query": query}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put("/queries/{query_id}")
async def update_saved_query(query_id: str, request: SavedQueryUpdateRequest):
    try:
        service = deps.get_saved_queries_service()
        updates = {k: v for k, v in request.model_dump().items() if v is not None}
        query = service.update_query(query_id, updates)
        if query is None:
            raise HTTPException(status_code=404, detail="Saved query not found")
        return {"success": True, "query": query}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/queries/{query_id}")
async def delete_saved_query(query_id: str):
    try:
        service = deps.get_saved_queries_service()
        removed = service.delete_query(query_id)
        if not removed:
            raise HTTPException(status_code=404, detail="Saved query not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/queries/{query_id}/run")
async def run_saved_query(query_id: str):
    try:
        service = deps.get_saved_queries_service()
        query = service.record_use(query_id)
        if query is None:
            raise HTTPException(status_code=404, detail="Saved query not found")
        return {"success": True, "query": query}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
