from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock


def test_duckdb_store_returns_empty_when_no_parquets(tmp_path: Path) -> None:
    from searchat.api.duckdb_store import DuckDBStore

    store = DuckDBStore(tmp_path)
    assert store.list_projects() == []
    assert store.list_project_summaries() == []
    assert store.list_conversations() == []
    assert store.count_conversations() == 0
    assert store.get_conversation_meta("missing") is None
    assert store.get_conversation_record("missing") is None
    stats = store.get_statistics()
    assert stats.total_conversations == 0


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


def test_duckdb_store_list_conversations_tool_filters(tmp_path: Path) -> None:
    from searchat.api.duckdb_store import DuckDBStore

    store = DuckDBStore(tmp_path)
    store._conversation_parquets = MagicMock(return_value=[tmp_path / "data" / "conversations" / "a.parquet"])  # type: ignore[method-assign]

    con = MagicMock()
    con.execute.return_value = con
    con.fetchall.return_value = []
    store._connect = MagicMock(return_value=con)  # type: ignore[method-assign]

    store.list_conversations(tool="opencode")
    query, _params = con.execute.call_args.args
    assert "project_id LIKE 'opencode-%'" in query

    store.list_conversations(tool="vibe")
    query2, _params2 = con.execute.call_args.args
    assert "project_id LIKE 'vibe-%'" in query2

    store.list_conversations(tool="claude")
    query3, _params3 = con.execute.call_args.args
    assert "project_id NOT LIKE 'opencode-%'" in query3
    assert "project_id NOT LIKE 'vibe-%'" in query3


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


def test_duckdb_store_validate_parquet_scan_scans_when_parquets_exist(tmp_path: Path) -> None:
    from searchat.api.duckdb_store import DuckDBStore

    store = DuckDBStore(tmp_path)

    con = MagicMock()
    con.execute.return_value = con
    con.fetchone.return_value = (1,)
    store._connect = MagicMock(return_value=con)  # type: ignore[method-assign]
    store._conversation_parquets = MagicMock(return_value=[tmp_path / "data" / "conversations" / "a.parquet"])  # type: ignore[method-assign]

    store.validate_parquet_scan()

    calls = [c.args[0] for c in con.execute.call_args_list]
    assert any("parquet_scan" in q for q in calls)


def test_duckdb_store_list_projects_returns_rows(tmp_path: Path) -> None:
    from searchat.api.duckdb_store import DuckDBStore

    store = DuckDBStore(tmp_path)
    store._conversation_parquets = MagicMock(return_value=[tmp_path / "data" / "conversations" / "a.parquet"])  # type: ignore[method-assign]

    con = MagicMock()
    con.execute.return_value = con
    con.fetchall.return_value = [("proj-b",), ("proj-a",)]
    store._connect = MagicMock(return_value=con)  # type: ignore[method-assign]

    assert store.list_projects() == ["proj-b", "proj-a"]


def test_duckdb_store_count_conversations_filters(tmp_path: Path) -> None:
    from searchat.api.duckdb_store import DuckDBStore

    store = DuckDBStore(tmp_path)
    store._conversation_parquets = MagicMock(return_value=[tmp_path / "data" / "conversations" / "a.parquet"])  # type: ignore[method-assign]

    con = MagicMock()
    con.execute.return_value = con
    con.fetchone.return_value = (3,)
    store._connect = MagicMock(return_value=con)  # type: ignore[method-assign]

    count = store.count_conversations(project_id="proj", tool="claude")
    assert count == 3

    query, _params = con.execute.call_args.args
    assert "project_id = ?" in query
    assert "project_id NOT LIKE 'opencode-%'" in query


def test_duckdb_store_count_conversations_handles_none_row(tmp_path: Path) -> None:
    from searchat.api.duckdb_store import DuckDBStore

    store = DuckDBStore(tmp_path)
    store._conversation_parquets = MagicMock(return_value=[tmp_path / "data" / "conversations" / "a.parquet"])  # type: ignore[method-assign]

    con = MagicMock()
    con.execute.return_value = con
    con.fetchone.return_value = None
    store._connect = MagicMock(return_value=con)  # type: ignore[method-assign]

    assert store.count_conversations() == 0


def test_duckdb_store_count_conversations_tool_and_date_filters(tmp_path: Path) -> None:
    from searchat.api.duckdb_store import DuckDBStore

    store = DuckDBStore(tmp_path)
    store._conversation_parquets = MagicMock(return_value=[tmp_path / "data" / "conversations" / "a.parquet"])  # type: ignore[method-assign]

    con = MagicMock()
    con.execute.return_value = con
    con.fetchone.return_value = (1,)
    store._connect = MagicMock(return_value=con)  # type: ignore[method-assign]

    date_from = datetime(2025, 1, 1, tzinfo=timezone.utc)
    date_to = datetime(2025, 2, 1, tzinfo=timezone.utc)
    store.count_conversations(tool="opencode", date_from=date_from, date_to=date_to)
    query, params = con.execute.call_args.args
    assert "project_id LIKE 'opencode-%'" in query
    assert "updated_at >= ?" in query
    assert "updated_at < ?" in query
    assert date_from in params
    assert date_to in params

    store.count_conversations(tool="vibe")
    query2, _params2 = con.execute.call_args.args
    assert "project_id LIKE 'vibe-%'" in query2


def test_duckdb_store_get_conversation_meta_returns_dict(tmp_path: Path) -> None:
    from searchat.api.duckdb_store import DuckDBStore

    store = DuckDBStore(tmp_path)
    store._conversation_parquets = MagicMock(return_value=[tmp_path / "data" / "conversations" / "a.parquet"])  # type: ignore[method-assign]

    con = MagicMock()
    con.execute.return_value = con
    con.fetchone.return_value = (
        "c1",
        "p1",
        "Title",
        "2025-01-01",
        "2025-01-02",
        3,
        "/tmp/c1.jsonl",
    )
    store._connect = MagicMock(return_value=con)  # type: ignore[method-assign]

    meta = store.get_conversation_meta("c1")
    assert meta is not None
    assert meta["conversation_id"] == "c1"
    assert meta["file_path"] == "/tmp/c1.jsonl"


def test_duckdb_store_get_conversation_meta_returns_none_when_missing(tmp_path: Path) -> None:
    from searchat.api.duckdb_store import DuckDBStore

    store = DuckDBStore(tmp_path)
    store._conversation_parquets = MagicMock(return_value=[tmp_path / "data" / "conversations" / "a.parquet"])  # type: ignore[method-assign]

    con = MagicMock()
    con.execute.return_value = con
    con.fetchone.return_value = None
    store._connect = MagicMock(return_value=con)  # type: ignore[method-assign]

    assert store.get_conversation_meta("missing") is None


def test_duckdb_store_get_conversation_record_returns_none_when_missing(tmp_path: Path) -> None:
    from searchat.api.duckdb_store import DuckDBStore

    store = DuckDBStore(tmp_path)
    store._conversation_parquets = MagicMock(return_value=[tmp_path / "data" / "conversations" / "a.parquet"])  # type: ignore[method-assign]

    con = MagicMock()
    con.execute.return_value = con
    con.fetchone.return_value = None
    store._connect = MagicMock(return_value=con)  # type: ignore[method-assign]

    assert store.get_conversation_record("missing") is None


def test_duckdb_store_get_statistics_converts_dates(tmp_path: Path) -> None:
    from searchat.api.duckdb_store import DuckDBStore

    store = DuckDBStore(tmp_path)
    store._conversation_parquets = MagicMock(return_value=[tmp_path / "data" / "conversations" / "a.parquet"])  # type: ignore[method-assign]

    con = MagicMock()
    con.execute.return_value = con
    con.fetchone.return_value = (
        4,
        20,
        5.0,
        2,
        datetime(2025, 1, 1, tzinfo=timezone.utc),
        "2025-02-01",
    )
    store._connect = MagicMock(return_value=con)  # type: ignore[method-assign]

    stats = store.get_statistics()
    assert stats.total_conversations == 4
    assert stats.earliest_date is not None
    assert stats.earliest_date.startswith("2025-01-01")
    assert stats.latest_date == "2025-02-01"


def test_duckdb_store_get_statistics_handles_none_dates(tmp_path: Path) -> None:
    from searchat.api.duckdb_store import DuckDBStore

    store = DuckDBStore(tmp_path)
    store._conversation_parquets = MagicMock(return_value=[tmp_path / "data" / "conversations" / "a.parquet"])  # type: ignore[method-assign]

    con = MagicMock()
    con.execute.return_value = con
    con.fetchone.return_value = (1, 1, 1.0, 1, None, None)
    store._connect = MagicMock(return_value=con)  # type: ignore[method-assign]

    stats = store.get_statistics()
    assert stats.earliest_date is None
    assert stats.latest_date is None
