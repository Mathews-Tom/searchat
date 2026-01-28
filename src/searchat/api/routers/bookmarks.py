"""Bookmarks endpoints for managing favorite conversations."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import searchat.api.dependencies as deps


router = APIRouter()


class BookmarkRequest(BaseModel):
    """Request model for adding/updating bookmark."""

    conversation_id: str
    notes: str = ''


class BookmarkNotesRequest(BaseModel):
    """Request model for updating bookmark notes."""

    notes: str


@router.get("/bookmarks")
async def get_bookmarks():
    """Get all bookmarked conversations."""
    try:
        bookmarks_service = deps.get_bookmarks_service()
        bookmarks = bookmarks_service.list_bookmarks()

        # Enrich bookmarks with conversation metadata
        store = deps.get_duckdb_store()
        enriched_bookmarks = []

        for bookmark in bookmarks:
            conv_id = bookmark['conversation_id']
            conv_meta = store.get_conversation_meta(conv_id)

            if conv_meta:
                enriched_bookmarks.append({
                    **bookmark,
                    'title': conv_meta['title'],
                    'project_id': conv_meta['project_id'],
                    'message_count': conv_meta['message_count'],
                    'created_at': conv_meta['created_at'].isoformat(),
                    'updated_at': conv_meta['updated_at'].isoformat(),
                })
            else:
                # Conversation not found in index, keep basic bookmark info
                enriched_bookmarks.append(bookmark)

        return {
            'total': len(enriched_bookmarks),
            'bookmarks': enriched_bookmarks
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bookmarks")
async def add_bookmark(request: BookmarkRequest):
    """Add a conversation to bookmarks."""
    try:
        bookmarks_service = deps.get_bookmarks_service()

        # Verify conversation exists
        store = deps.get_duckdb_store()
        conv_meta = store.get_conversation_meta(request.conversation_id)

        if not conv_meta:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation {request.conversation_id} not found"
            )

        bookmark = bookmarks_service.add_bookmark(
            request.conversation_id,
            request.notes
        )

        return {
            'success': True,
            'bookmark': bookmark
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/bookmarks/{conversation_id}")
async def remove_bookmark(conversation_id: str):
    """Remove a conversation from bookmarks."""
    try:
        bookmarks_service = deps.get_bookmarks_service()
        removed = bookmarks_service.remove_bookmark(conversation_id)

        if not removed:
            raise HTTPException(
                status_code=404,
                detail=f"Bookmark for conversation {conversation_id} not found"
            )

        return {
            'success': True,
            'message': f'Bookmark removed for conversation {conversation_id}'
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bookmarks/{conversation_id}")
async def get_bookmark(conversation_id: str):
    """Get bookmark status for a conversation."""
    try:
        bookmarks_service = deps.get_bookmarks_service()
        bookmark = bookmarks_service.get_bookmark(conversation_id)

        if bookmark:
            return {
                'is_bookmarked': True,
                'bookmark': bookmark
            }
        else:
            return {
                'is_bookmarked': False,
                'bookmark': None
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/bookmarks/{conversation_id}/notes")
async def update_bookmark_notes(
    conversation_id: str,
    request: BookmarkNotesRequest
):
    """Update notes for a bookmark."""
    try:
        bookmarks_service = deps.get_bookmarks_service()
        updated = bookmarks_service.update_notes(conversation_id, request.notes)

        if not updated:
            raise HTTPException(
                status_code=404,
                detail=f"Bookmark for conversation {conversation_id} not found"
            )

        return {
            'success': True,
            'message': 'Notes updated successfully'
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
