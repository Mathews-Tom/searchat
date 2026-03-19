"""Bookmarks endpoints for managing favorite conversations."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import searchat.api.dependencies as deps
from searchat.api.contracts import (
    serialize_bookmark_mutation_payload,
    serialize_bookmark_payload,
    serialize_bookmark_status_payload,
    serialize_bookmarks_payload,
    serialize_success_message_payload,
)
from searchat.api.dataset_access import get_dataset_store
from searchat.contracts.errors import bookmark_not_found_message, conversation_not_found_message
from searchat.contracts.errors import bookmark_notes_updated_message, bookmark_removed_message


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
        store = get_dataset_store(None).store
        enriched_bookmarks = []

        for bookmark in bookmarks:
            conv_id = bookmark["conversation_id"]
            conv_meta = store.get_conversation_meta(conv_id)

            if conv_meta:
                enriched_bookmarks.append(
                    serialize_bookmark_payload(bookmark, conversation=conv_meta)
                )
            else:
                # Conversation not found in index, keep basic bookmark info
                enriched_bookmarks.append(serialize_bookmark_payload(bookmark))

        return serialize_bookmarks_payload(enriched_bookmarks)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bookmarks")
async def add_bookmark(request: BookmarkRequest):
    """Add a conversation to bookmarks."""
    try:
        bookmarks_service = deps.get_bookmarks_service()

        # Verify conversation exists
        store = get_dataset_store(None).store
        conv_meta = store.get_conversation_meta(request.conversation_id)

        if not conv_meta:
            raise HTTPException(
                status_code=404,
                detail=conversation_not_found_message(request.conversation_id),
            )

        bookmark = bookmarks_service.add_bookmark(
            request.conversation_id,
            request.notes
        )

        return serialize_bookmark_mutation_payload(bookmark)

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
                detail=bookmark_not_found_message(conversation_id),
            )

        return serialize_success_message_payload(bookmark_removed_message(conversation_id))

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

        return serialize_bookmark_status_payload(bookmark)

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
                detail=bookmark_not_found_message(conversation_id),
            )

        return serialize_success_message_payload(bookmark_notes_updated_message())

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
