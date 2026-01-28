"""Bookmarks service for managing favorite conversations."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from searchat.config import Config


class BookmarksService:
    """Service for managing conversation bookmarks."""

    def __init__(self, config: Config):
        """Initialize bookmarks service."""
        self.config = config
        self.bookmarks_file = Path(config.paths.search_directory) / 'bookmarks.json'
        self._ensure_file()

    def _ensure_file(self) -> None:
        """Ensure bookmarks file exists."""
        if not self.bookmarks_file.exists():
            self.bookmarks_file.parent.mkdir(parents=True, exist_ok=True)
            self._save_bookmarks({})

    def _load_bookmarks(self) -> dict[str, dict[str, Any]]:
        """Load bookmarks from file."""
        try:
            with open(self.bookmarks_file, encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _save_bookmarks(self, bookmarks: dict[str, dict[str, Any]]) -> None:
        """Save bookmarks to file."""
        with open(self.bookmarks_file, 'w', encoding='utf-8') as f:
            json.dump(bookmarks, f, indent=2)

    def add_bookmark(
        self,
        conversation_id: str,
        notes: str = ''
    ) -> dict[str, Any]:
        """Add a conversation to bookmarks."""
        bookmarks = self._load_bookmarks()

        bookmark = {
            'conversation_id': conversation_id,
            'added_at': datetime.now().isoformat(),
            'notes': notes
        }

        bookmarks[conversation_id] = bookmark
        self._save_bookmarks(bookmarks)

        return bookmark

    def remove_bookmark(self, conversation_id: str) -> bool:
        """Remove a conversation from bookmarks."""
        bookmarks = self._load_bookmarks()

        if conversation_id in bookmarks:
            del bookmarks[conversation_id]
            self._save_bookmarks(bookmarks)
            return True

        return False

    def get_bookmark(self, conversation_id: str) -> dict[str, Any] | None:
        """Get a specific bookmark."""
        bookmarks = self._load_bookmarks()
        return bookmarks.get(conversation_id)

    def list_bookmarks(self) -> list[dict[str, Any]]:
        """List all bookmarks, sorted by added_at (newest first)."""
        bookmarks = self._load_bookmarks()

        # Convert to list and sort
        bookmark_list = list(bookmarks.values())
        bookmark_list.sort(
            key=lambda b: b.get('added_at', ''),
            reverse=True
        )

        return bookmark_list

    def is_bookmarked(self, conversation_id: str) -> bool:
        """Check if a conversation is bookmarked."""
        bookmarks = self._load_bookmarks()
        return conversation_id in bookmarks

    def update_notes(self, conversation_id: str, notes: str) -> bool:
        """Update notes for a bookmark."""
        bookmarks = self._load_bookmarks()

        if conversation_id in bookmarks:
            bookmarks[conversation_id]['notes'] = notes
            self._save_bookmarks(bookmarks)
            return True

        return False
