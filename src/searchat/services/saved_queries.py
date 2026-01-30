"""Saved queries service for managing reusable searches."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from searchat.config import Config


class SavedQueriesService:
    """Service for managing saved search queries."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._queries_file = Path(config.paths.search_directory) / "saved_queries.json"
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not self._queries_file.exists():
            self._queries_file.parent.mkdir(parents=True, exist_ok=True)
            self._save_queries({})

    def _load_queries(self) -> dict[str, dict[str, Any]]:
        with open(self._queries_file, encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError("Saved queries file is invalid.")
        return data

    def _save_queries(self, queries: dict[str, dict[str, Any]]) -> None:
        with open(self._queries_file, "w", encoding="utf-8") as handle:
            json.dump(queries, handle, indent=2)

    def list_queries(self) -> list[dict[str, Any]]:
        queries = self._load_queries()
        query_list = list(queries.values())
        for query in query_list:
            created_at = query.get("created_at")
            if not isinstance(created_at, str) or not created_at:
                raise ValueError("Saved query is missing created_at.")
        query_list.sort(key=lambda q: q["created_at"], reverse=True)
        return query_list

    def get_query(self, query_id: str) -> dict[str, Any] | None:
        queries = self._load_queries()
        return queries.get(query_id)

    def create_query(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = payload.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Saved query name is required.")

        query_text = payload.get("query")
        if not isinstance(query_text, str):
            raise ValueError("Saved query text is required.")

        filters = payload.get("filters")
        if not isinstance(filters, dict):
            raise ValueError("Saved query filters must be provided.")

        mode = payload.get("mode")
        if not isinstance(mode, str) or not mode.strip():
            raise ValueError("Saved query mode is required.")

        queries = self._load_queries()
        query_id = str(uuid4())
        timestamp = datetime.now().isoformat()
        query = {
            "id": query_id,
            "name": name,
            "description": payload.get("description"),
            "query": query_text,
            "filters": filters,
            "mode": mode,
            "created_at": timestamp,
            "last_used": None,
            "use_count": 0,
        }
        queries[query_id] = query
        self._save_queries(queries)
        return query

    def update_query(self, query_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        queries = self._load_queries()
        query = queries.get(query_id)
        if query is None:
            return None

        if "name" in updates:
            name = updates["name"]
            if not isinstance(name, str) or not name.strip():
                raise ValueError("Saved query name is required.")

        if "query" in updates:
            query_text = updates["query"]
            if not isinstance(query_text, str):
                raise ValueError("Saved query text is required.")

        if "filters" in updates:
            filters = updates["filters"]
            if not isinstance(filters, dict):
                raise ValueError("Saved query filters must be provided.")

        if "mode" in updates:
            mode = updates["mode"]
            if not isinstance(mode, str) or not mode.strip():
                raise ValueError("Saved query mode is required.")

        for field in ("name", "description", "query", "filters", "mode"):
            if field in updates:
                query[field] = updates[field]

        queries[query_id] = query
        self._save_queries(queries)
        return query

    def delete_query(self, query_id: str) -> bool:
        queries = self._load_queries()
        if query_id in queries:
            del queries[query_id]
            self._save_queries(queries)
            return True
        return False

    def record_use(self, query_id: str) -> dict[str, Any] | None:
        queries = self._load_queries()
        query = queries.get(query_id)
        if query is None:
            return None

        query["last_used"] = datetime.now().isoformat()
        use_count = query.get("use_count")
        if not isinstance(use_count, int):
            raise ValueError("Saved query use_count is invalid.")
        query["use_count"] = use_count + 1
        queries[query_id] = query
        self._save_queries(queries)
        return query
