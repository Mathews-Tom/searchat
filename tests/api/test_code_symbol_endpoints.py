from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient

from searchat.api.app import app
from searchat.api.duckdb_store import DuckDBStore
from searchat.models.schemas import CODE_BLOCK_SCHEMA


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
            "classes": ["Greeter"],
            "imports": ["os"],
            "code": "import os\n\n" "class Greeter:\n" "    pass\n\n" "def greet():\n" "    print('hi')\n",
            "code_hash": "abc",
            "lines": 7,
        }
    ]
    table = pa.Table.from_pylist(rows, schema=CODE_BLOCK_SCHEMA)
    pq.write_table(table, code_dir / "project_project-one.parquet")


@pytest.mark.unit
def test_conversation_code_symbols_returns_aggregates(client: TestClient, tmp_path: Path) -> None:
    search_dir = tmp_path / "search"
    _write_code_parquet(search_dir)

    store = DuckDBStore(search_dir)

    with patch(
        "searchat.api.routers.code.deps.resolve_dataset_search_dir",
        return_value=(search_dir, None),
    ), patch(
        "searchat.api.routers.code.deps.get_duckdb_store_for",
        return_value=store,
    ):
        resp = client.get("/api/conversation/conv-1/code-symbols")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["conversation_id"] == "conv-1"
    assert payload["functions"] == ["greet"]
    assert payload["classes"] == ["Greeter"]
    assert payload["imports"] == ["os"]


@pytest.mark.unit
def test_code_functions_endpoint_filters_by_name(client: TestClient, tmp_path: Path) -> None:
    search_dir = tmp_path / "search"
    _write_code_parquet(search_dir)

    store = DuckDBStore(search_dir)

    with patch(
        "searchat.api.routers.code.deps.resolve_dataset_search_dir",
        return_value=(search_dir, None),
    ), patch(
        "searchat.api.routers.code.deps.get_duckdb_store_for",
        return_value=store,
    ):
        resp = client.get("/api/code/functions?name=greet")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["total"] == 1
    assert len(payload["results"]) == 1


@pytest.mark.unit
def test_code_imports_endpoint_filters_by_module(client: TestClient, tmp_path: Path) -> None:
    search_dir = tmp_path / "search"
    _write_code_parquet(search_dir)

    store = DuckDBStore(search_dir)

    with patch(
        "searchat.api.routers.code.deps.resolve_dataset_search_dir",
        return_value=(search_dir, None),
    ), patch(
        "searchat.api.routers.code.deps.get_duckdb_store_for",
        return_value=store,
    ):
        resp = client.get("/api/code/imports?module=os")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["total"] == 1
    assert len(payload["results"]) == 1


@pytest.mark.unit
def test_code_symbol_endpoints_return_503_when_no_code_index(client: TestClient, tmp_path: Path) -> None:
    search_dir = tmp_path / "search"
    store = DuckDBStore(search_dir)

    with patch(
        "searchat.api.routers.code.deps.resolve_dataset_search_dir",
        return_value=(search_dir, None),
    ), patch(
        "searchat.api.routers.code.deps.get_duckdb_store_for",
        return_value=store,
    ):
        resp = client.get("/api/conversation/conv-1/code-symbols")
        resp2 = client.get("/api/code/functions?name=greet")

    assert resp.status_code == 503
    assert resp2.status_code == 503
