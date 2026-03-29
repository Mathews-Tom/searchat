from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient

from searchat.api.app import app
from searchat.models.schemas import CODE_BLOCK_SCHEMA


class _InMemoryStore:
    """Minimal store with _connect() for ad-hoc Parquet queries."""

    def _connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(database=":memory:")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _write_code_parquet(search_dir: Path) -> None:
    code_dir = search_dir / "data" / "code"
    code_dir.mkdir(parents=True, exist_ok=True)

    now = datetime(2026, 2, 2, 12, 0, 0)
    rows = [
        {
            "conversation_id": "conv-1",
            "project_id": "project-one",
            "connector": "claude",
            "file_path": "/tmp/conv-1.jsonl",
            "title": "Example",
            "conversation_created_at": now,
            "conversation_updated_at": now,
            "message_index": 1,
            "block_index": 0,
            "role": "assistant",
            "message_timestamp": now,
            "fence_language": "python",
            "language": "python",
            "language_source": "fence",
            "functions": ["greet"],
            "classes": [],
            "imports": ["os"],
            "code": "import os\n\n" "def greet():\n" "    print('hi')\n",
            "code_hash": "abc",
            "lines": 4,
        }
    ]
    table = pa.Table.from_pylist(rows, schema=CODE_BLOCK_SCHEMA)
    pq.write_table(table, code_dir / "project_project-one.parquet")


@pytest.mark.unit
def test_search_code_returns_results(client: TestClient, tmp_path: Path) -> None:
    search_dir = tmp_path / "search"
    _write_code_parquet(search_dir)

    store = _InMemoryStore()

    with patch(
        "searchat.api.routers.search.get_dataset_store",
        return_value=SimpleNamespace(search_dir=search_dir, snapshot_name=None, store=store),
    ):
        resp = client.get("/api/search/code?q=print")

    assert resp.status_code == 200
    payload = resp.json()
    assert list(payload) == ["results", "total", "limit", "offset", "has_more"]
    assert payload["total"] == 1
    assert len(payload["results"]) == 1
    assert payload["results"][0]["language"] == "python"


@pytest.mark.unit
def test_search_code_filters_by_function_name(client: TestClient, tmp_path: Path) -> None:
    search_dir = tmp_path / "search"
    _write_code_parquet(search_dir)

    store = _InMemoryStore()

    with patch(
        "searchat.api.routers.search.get_dataset_store",
        return_value=SimpleNamespace(search_dir=search_dir, snapshot_name=None, store=store),
    ):
        resp = client.get("/api/search/code?function=greet")

    assert resp.status_code == 200
    payload = resp.json()
    assert list(payload) == ["results", "total", "limit", "offset", "has_more"]
    assert payload["total"] == 1
    assert len(payload["results"]) == 1


@pytest.mark.unit
def test_search_code_returns_503_when_no_code_index(client: TestClient, tmp_path: Path) -> None:
    search_dir = tmp_path / "search"
    store = _InMemoryStore()

    with patch(
        "searchat.api.routers.search.get_dataset_store",
        return_value=SimpleNamespace(search_dir=search_dir, snapshot_name=None, store=store),
    ):
        resp = client.get("/api/search/code?q=print")

    assert resp.status_code == 503
    assert resp.json()["detail"] == "Code index not found. Rebuild the index to enable /api/search/code."


@pytest.mark.unit
def test_search_code_returns_500_on_store_error(client: TestClient, tmp_path: Path) -> None:
    search_dir = tmp_path / "search"
    code_dir = search_dir / "data" / "code"
    code_dir.mkdir(parents=True, exist_ok=True)
    (code_dir / "dummy.parquet").write_text("x")

    class BoomStore:
        def _connect(self):
            raise RuntimeError("boom")

    with patch(
        "searchat.api.routers.search.get_dataset_store",
        return_value=SimpleNamespace(search_dir=search_dir, snapshot_name=None, store=BoomStore()),
    ):
        resp = client.get("/api/search/code?q=print")

    assert resp.status_code == 500
    assert resp.json()["detail"] == "Internal server error"
