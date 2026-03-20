"""Saved queries endpoints for managing reusable searches."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from searchat.api.contracts import (
    serialize_saved_queries_payload,
    serialize_saved_query_mutation_payload,
    serialize_success_flag_payload,
)
import searchat.api.dependencies as deps
from searchat.contracts.errors import (
    internal_server_error_message,
    saved_query_not_found_message,
    saved_query_validation_message,
)


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
        queries = service.list_queries()
        return serialize_saved_queries_payload(queries)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=internal_server_error_message()) from exc


@router.post("/queries")
async def create_saved_query(request: SavedQueryCreateRequest):
    try:
        service = deps.get_saved_queries_service()
        query = service.create_query(request.model_dump())
        return serialize_saved_query_mutation_payload(query)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=saved_query_validation_message(str(exc))) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=internal_server_error_message()) from exc


@router.put("/queries/{query_id}")
async def update_saved_query(query_id: str, request: SavedQueryUpdateRequest):
    try:
        service = deps.get_saved_queries_service()
        updates = {k: v for k, v in request.model_dump().items() if v is not None}
        query = service.update_query(query_id, updates)
        if query is None:
            raise HTTPException(status_code=404, detail=saved_query_not_found_message())
        return serialize_saved_query_mutation_payload(query)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=saved_query_validation_message(str(exc))) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=internal_server_error_message()) from exc


@router.delete("/queries/{query_id}")
async def delete_saved_query(query_id: str):
    try:
        service = deps.get_saved_queries_service()
        removed = service.delete_query(query_id)
        if not removed:
            raise HTTPException(status_code=404, detail=saved_query_not_found_message())
        return serialize_success_flag_payload()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=internal_server_error_message()) from exc


@router.post("/queries/{query_id}/run")
async def run_saved_query(query_id: str):
    try:
        service = deps.get_saved_queries_service()
        query = service.record_use(query_id)
        if query is None:
            raise HTTPException(status_code=404, detail=saved_query_not_found_message())
        return serialize_saved_query_mutation_payload(query)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=saved_query_validation_message(str(exc))) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=internal_server_error_message()) from exc
