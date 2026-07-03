"""End-to-end: an omp-parsed, Parquet-indexed conversation is searchable
via the ``tool=omp`` filter and correctly excluded from other tool filters.
"""
from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from searchat.config import Config
from searchat.core.connectors.omp import OmpConnector
from searchat.core.unified_search import UnifiedSearchEngine
from searchat.models import CONVERSATION_SCHEMA, ConversationRecord, SearchFilters, SearchMode

OMP_FIXTURE = Path(
    "tests/fixtures/connectors/omp/sessions/-tmp-demo-project/"
    "2026-03-29T10-00-00-000Z_01900000-0000-7000-8000-000000000001.jsonl"
)


def _record_dict(record: ConversationRecord) -> dict:
    """Mirror core/indexer.py::ConversationIndexer._record_to_dict."""
    return {
        "conversation_id": record.conversation_id,
        "project_id": record.project_id,
        "file_path": record.file_path,
        "title": record.title,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "message_count": record.message_count,
        "messages": [
            {
                "sequence": m.sequence,
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp,
                "has_code": m.has_code,
                "code_blocks": m.code_blocks,
            }
            for m in record.messages
        ],
        "full_text": record.full_text,
        "embedding_id": record.embedding_id,
        "file_hash": record.file_hash,
        "indexed_at": record.indexed_at,
        "files_mentioned": record.files_mentioned,
        "git_branch": record.git_branch,
    }


def test_tool_omp_filter_returns_omp_results_and_excludes_others(tmp_path: Path) -> None:
    search_dir = tmp_path / "search"
    conversations_dir = search_dir / "data" / "conversations"
    conversations_dir.mkdir(parents=True)

    # Real connector parsing a real fixture file, copied into a path that
    # mirrors the production ~/.omp/agent/sessions/<slug>/<file>.jsonl
    # layout -- the SQL tool filter keys off that path shape.
    omp_session_dir = tmp_path / "home" / ".omp" / "agent" / "sessions" / "-tmp-demo-project"
    omp_session_dir.mkdir(parents=True)
    omp_path = omp_session_dir / OMP_FIXTURE.name
    omp_path.write_text(OMP_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")

    omp_record = OmpConnector().parse(omp_path, embedding_id=0)
    omp_row = _record_dict(omp_record)

    # A non-omp conversation living under a claude-shaped path, so the tool
    # filter has something real to exclude/include on both sides.
    claude_row = dict(omp_row)
    claude_row.update(
        conversation_id="claude-conv-1",
        project_id="claude-proj",
        file_path=str(tmp_path / "home" / ".claude" / "projects" / "claude-proj" / "claude-conv-1.jsonl"),
        title="Unrelated claude conversation",
    )

    table = pa.Table.from_pylist([omp_row, claude_row], schema=CONVERSATION_SCHEMA)
    pq.write_table(table, conversations_dir / "project_mixed.parquet")

    engine = UnifiedSearchEngine(search_dir, Config.load())

    omp_results = engine.search("*", mode=SearchMode.KEYWORD, filters=SearchFilters(tool="omp"))
    omp_ids = {r.conversation_id for r in omp_results.results}
    assert omp_record.conversation_id in omp_ids
    assert "claude-conv-1" not in omp_ids

    claude_results = engine.search("*", mode=SearchMode.KEYWORD, filters=SearchFilters(tool="claude"))
    claude_ids = {r.conversation_id for r in claude_results.results}
    assert "claude-conv-1" in claude_ids
    assert omp_record.conversation_id not in claude_ids

    unfiltered_results = engine.search("*", mode=SearchMode.KEYWORD, filters=None)
    unfiltered_ids = {r.conversation_id for r in unfiltered_results.results}
    assert {omp_record.conversation_id, "claude-conv-1"} <= unfiltered_ids
