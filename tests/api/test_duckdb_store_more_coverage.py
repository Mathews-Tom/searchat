from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock


def test_duckdb_store_returns_empty_when_no_parquets(tmp_path: Path) -> None:
    from searchat.api.duckdb_store import DuckDBStore

    store = DuckDBStore(tmp_path)
    assert store.list_projects() == []
    assert store.list_conversations() == []
    assert store.get_conversation_meta("missing") is None


def test_duckdb_store_list_conversations_builds_where_and_params(tmp_path: Path) -> None:
    from searchat.api.duckdb_store import DuckDBStore

    store = DuckDBStore(tmp_path)

    # Pretend parquet exists.
    store._conversation_parquets = MagicMock(return_value=[tmp_path / "data" / "conversations" / "a.parquet"])  # type: ignore[method-assign]

    con = MagicMock()
    con.execute.return_value = con
    con.fetchall.return_value = [
        (
            "c1",
            "p1",
            "t1",
            "2025-01-01",
            "2025-01-02",
            3,
            "/tmp/c1.jsonl",
            "full text",
        )
    ]
    store._connect = MagicMock(return_value=con)  # type: ignore[method-assign]

    date_from = datetime(2025, 1, 1, tzinfo=timezone.utc)
    date_to = datetime(2025, 2, 1, tzinfo=timezone.utc)
    rows = store.list_conversations(
        sort_by="invalid",
        project_id="p1",
        date_from=date_from,
        date_to=date_to,
        limit=10,
        offset=5,
    )

    assert rows[0]["conversation_id"] == "c1"

    query, params = con.execute.call_args.args
    assert "project_id = ?" in query
    assert "updated_at >= ?" in query
    assert "updated_at < ?" in query
    assert params[1:] == ["p1", date_from, date_to, 10, 5]

    assert "LIMIT ?" in query
    assert "OFFSET ?" in query
    assert params[-2:] == [10, 5]


def test_duckdb_store_get_statistics_handles_none_row(tmp_path: Path) -> None:
    from searchat.api.duckdb_store import DuckDBStore

    store = DuckDBStore(tmp_path)
    store._conversation_parquets = MagicMock(return_value=[tmp_path / "data" / "conversations" / "a.parquet"])  # type: ignore[method-assign]

    con = MagicMock()
    con.execute.return_value = con
    con.fetchone.return_value = None
    store._connect = MagicMock(return_value=con)  # type: ignore[method-assign]

    stats = store.get_statistics()
    assert stats.total_conversations == 0
    assert stats.total_messages == 0
    assert stats.total_projects == 0


def test_duckdb_store_validate_parquet_scan_runs_select(tmp_path: Path) -> None:
    from searchat.api.duckdb_store import DuckDBStore

    store = DuckDBStore(tmp_path)

    con = MagicMock()
    con.execute.return_value = con
    con.fetchone.return_value = (1,)
    store._connect = MagicMock(return_value=con)  # type: ignore[method-assign]
    store._conversation_parquets = MagicMock(return_value=[])  # type: ignore[method-assign]

    store.validate_parquet_scan()
    con.execute.assert_called()
