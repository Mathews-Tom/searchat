"""Palace API router — search and management endpoints for distilled memories."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from searchat.api.dependencies import get_config, get_palace_query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/palace", tags=["palace"])


class PalaceSearchRequest(BaseModel):
    query: str
    limit: int = 20
    project_id: str | None = None


class PalaceSearchResultItem(BaseModel):
    object_id: str
    conversation_id: str
    project_id: str
    ply_start: int
    ply_end: int
    exchange_core: str
    specific_context: str
    files_touched: list[dict]
    rooms: list[dict]
    score: float
    keyword_score: float = 0.0
    semantic_score: float = 0.0


class PalaceSearchResponse(BaseModel):
    results: list[PalaceSearchResultItem]
    total_count: int


class RoomItem(BaseModel):
    room_id: str
    room_type: str
    room_key: str
    room_label: str
    project_id: str | None
    object_count: int


class RoomObjectItem(BaseModel):
    object_id: str
    conversation_id: str
    project_id: str
    ply_start: int
    ply_end: int
    exchange_core: str
    specific_context: str


class PalaceStatsResponse(BaseModel):
    total_objects: int
    total_rooms: int
    total_conversations: int
    enabled: bool


@router.get("/stats", response_model=PalaceStatsResponse)
async def palace_stats() -> PalaceStatsResponse:
    """Get palace statistics."""
    config = get_config()
    if not config.palace.enabled:
        return PalaceStatsResponse(
            total_objects=0, total_rooms=0, total_conversations=0, enabled=False,
        )
    try:
        pq = get_palace_query()
        stats = pq.storage.get_stats()
        return PalaceStatsResponse(enabled=True, **stats)
    except RuntimeError:
        return PalaceStatsResponse(
            total_objects=0, total_rooms=0, total_conversations=0, enabled=True,
        )


@router.post("/search", response_model=PalaceSearchResponse)
async def palace_search(request: PalaceSearchRequest) -> PalaceSearchResponse:
    """Search distilled palace objects."""
    config = get_config()
    if not config.palace.enabled:
        raise HTTPException(status_code=400, detail="Palace is not enabled")

    pq = get_palace_query()
    project_ids = [request.project_id] if request.project_id else None
    results = pq.search_hybrid(
        query=request.query,
        limit=request.limit,
        project_ids=project_ids,
    )

    items = []
    for r in results:
        items.append(PalaceSearchResultItem(
            object_id=r.object_id,
            conversation_id=r.conversation_id,
            project_id=r.project_id,
            ply_start=r.ply_start,
            ply_end=r.ply_end,
            exchange_core=r.exchange_core,
            specific_context=r.specific_context,
            files_touched=[{"path": f.path, "action": f.action} for f in r.files_touched],
            rooms=[{
                "room_id": rm.room_id, "room_type": rm.room_type,
                "room_key": rm.room_key, "room_label": rm.room_label,
            } for rm in r.rooms],
            score=r.score,
            keyword_score=r.keyword_score,
            semantic_score=r.semantic_score,
        ))

    return PalaceSearchResponse(results=items, total_count=len(items))


@router.get("/rooms")
async def list_rooms(
    project_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[RoomItem]:
    """List all palace rooms."""
    config = get_config()
    if not config.palace.enabled:
        raise HTTPException(status_code=400, detail="Palace is not enabled")

    pq = get_palace_query()
    rooms = pq.storage.get_all_rooms(project_id=project_id)[:limit]
    return [
        RoomItem(
            room_id=r.room_id, room_type=r.room_type, room_key=r.room_key,
            room_label=r.room_label, project_id=r.project_id,
            object_count=r.object_count,
        )
        for r in rooms
    ]


@router.get("/rooms/{room_id}/objects")
async def room_objects(room_id: str) -> list[RoomObjectItem]:
    """Get all objects in a room."""
    config = get_config()
    if not config.palace.enabled:
        raise HTTPException(status_code=400, detail="Palace is not enabled")

    pq = get_palace_query()
    objects = pq.walk_room(room_id)
    return [
        RoomObjectItem(
            object_id=o.object_id, conversation_id=o.conversation_id,
            project_id=o.project_id, ply_start=o.ply_start, ply_end=o.ply_end,
            exchange_core=o.exchange_core, specific_context=o.specific_context,
        )
        for o in objects
    ]


@router.get("/rooms/search")
async def find_rooms(
    query: str = Query(...),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[RoomItem]:
    """Search rooms by query."""
    config = get_config()
    if not config.palace.enabled:
        raise HTTPException(status_code=400, detail="Palace is not enabled")

    pq = get_palace_query()
    rooms = pq.find_rooms(query, limit=limit)
    return [
        RoomItem(
            room_id=r.room_id, room_type=r.room_type, room_key=r.room_key,
            room_label=r.room_label, project_id=r.project_id,
            object_count=r.object_count,
        )
        for r in rooms
    ]
