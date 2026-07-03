"""Unit tests for `searchat.services.dedup_detection` (M11).

Covers the milestone acceptance criteria: a fixture near-duplicate pair
(same content ingested via two different connectors) is flagged above
`similarity_threshold`; a fixture pair of genuinely distinct conversations
is not flagged; same-connector pairs are never compared (cross-agent
detection only); the standalone (no live connection) path opens its own
READ-ONLY connection and degrades gracefully when the database doesn't
exist yet.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import pytest

from searchat.services.dedup_detection import (
    DEFAULT_SIMILARITY_THRESHOLD,
    DuplicateSuggestion,
    find_near_duplicates,
)


def _seed_connection(
    con: duckdb.DuckDBPyConnection,
    *,
    conversations: tuple[dict[str, Any], ...],
    embedding_dim: int,
) -> None:
    """Minimal hand-built schema covering only what `find_near_duplicates`
    reads: `conversations`, `exchanges`, `verbatim_embeddings`,
    `source_file_state`. Mirrors `test_compaction.py`'s `_seed_minimal_db`
    convention of a small fixed-width embedding column rather than the
    full 384-dim production schema.
    """
    con.execute(
        "CREATE TABLE conversations(conversation_id VARCHAR PRIMARY KEY, "
        "title VARCHAR, file_path VARCHAR)"
    )
    con.execute("CREATE TABLE exchanges(exchange_id VARCHAR PRIMARY KEY, conversation_id VARCHAR)")
    con.execute(
        f"CREATE TABLE verbatim_embeddings(exchange_id VARCHAR PRIMARY KEY, "
        f"embedding FLOAT[{embedding_dim}])"
    )
    con.execute(
        "CREATE TABLE source_file_state(file_path VARCHAR PRIMARY KEY, "
        "conversation_id VARCHAR, connector_name VARCHAR, status VARCHAR)"
    )
    for conv in conversations:
        con.execute(
            "INSERT INTO conversations VALUES (?, ?, ?)",
            [conv["conversation_id"], conv["title"], conv["file_path"]],
        )
        con.execute(
            "INSERT INTO source_file_state VALUES (?, ?, ?, 'indexed')",
            [conv["file_path"], conv["conversation_id"], conv.get("connector_name")],
        )
        for idx, embedding in enumerate(conv.get("embeddings", ())):
            exchange_id = f"{conv['conversation_id']}-e{idx}"
            con.execute(
                "INSERT INTO exchanges VALUES (?, ?)", [exchange_id, conv["conversation_id"]]
            )
            con.execute(
                "INSERT INTO verbatim_embeddings VALUES (?, ?)", [exchange_id, embedding]
            )


def _build_fixture_db(db_path: Path, *, conversations: tuple[dict[str, Any], ...], embedding_dim: int) -> None:
    con = duckdb.connect(str(db_path))
    try:
        _seed_connection(con, conversations=conversations, embedding_dim=embedding_dim)
        con.execute("CHECKPOINT")
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Milestone acceptance: near-duplicate pair flagged, distinct pair is not.
# ---------------------------------------------------------------------------


_SAME_CONTENT_VECTOR = [1.0, 0.0, 0.0, 0.0]
_DISTINCT_VECTOR_A = [1.0, 0.0, 0.0, 0.0]
_DISTINCT_VECTOR_B = [0.0, 1.0, 0.0, 0.0]


@pytest.mark.unit
def test_find_near_duplicates_flags_cross_connector_near_duplicate_pair() -> None:
    """Same content ingested via two different connectors (claude, codex) is
    flagged above the default similarity threshold."""
    con = duckdb.connect(":memory:")
    _seed_connection(
        con,
        conversations=(
            {
                "conversation_id": "claude-conv-1",
                "title": "Debugging the auth flow",
                "file_path": "/home/user/.claude/projects/p/conv1.jsonl",
                "connector_name": "claude",
                "embeddings": [_SAME_CONTENT_VECTOR, _SAME_CONTENT_VECTOR],
            },
            {
                "conversation_id": "codex-conv-1",
                "title": "Debugging the auth flow",
                "file_path": "/home/user/.codex/sessions/conv1.jsonl",
                "connector_name": "codex",
                "embeddings": [_SAME_CONTENT_VECTOR, _SAME_CONTENT_VECTOR],
            },
        ),
        embedding_dim=4,
    )

    suggestions = find_near_duplicates(Path("unused"), connection=con, similarity_threshold=0.92)

    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert isinstance(suggestion, DuplicateSuggestion)
    assert {suggestion.connector_a, suggestion.connector_b} == {"claude", "codex"}
    assert {suggestion.conversation_id_a, suggestion.conversation_id_b} == {
        "claude-conv-1",
        "codex-conv-1",
    }
    assert suggestion.similarity == pytest.approx(1.0)


@pytest.mark.unit
def test_find_near_duplicates_does_not_flag_genuinely_distinct_conversations() -> None:
    """Orthogonal embeddings (unrelated content) across two connectors stay
    below threshold and are never flagged."""
    con = duckdb.connect(":memory:")
    _seed_connection(
        con,
        conversations=(
            {
                "conversation_id": "claude-conv-2",
                "title": "Refactoring the parser",
                "file_path": "/home/user/.claude/projects/p/conv2.jsonl",
                "connector_name": "claude",
                "embeddings": [_DISTINCT_VECTOR_A],
            },
            {
                "conversation_id": "codex-conv-2",
                "title": "Deploying the CI pipeline",
                "file_path": "/home/user/.codex/sessions/conv2.jsonl",
                "connector_name": "codex",
                "embeddings": [_DISTINCT_VECTOR_B],
            },
        ),
        embedding_dim=4,
    )

    suggestions = find_near_duplicates(Path("unused"), connection=con, similarity_threshold=0.92)

    assert suggestions == ()


@pytest.mark.unit
def test_find_near_duplicates_ignores_same_connector_pairs() -> None:
    """Identical content from the SAME connector is never compared -- this
    milestone is cross-agent duplicate detection specifically."""
    con = duckdb.connect(":memory:")
    _seed_connection(
        con,
        conversations=(
            {
                "conversation_id": "claude-conv-3",
                "title": "Debugging the auth flow",
                "file_path": "/home/user/.claude/projects/p/conv3.jsonl",
                "connector_name": "claude",
                "embeddings": [_SAME_CONTENT_VECTOR],
            },
            {
                "conversation_id": "claude-conv-4",
                "title": "Debugging the auth flow (copy)",
                "file_path": "/home/user/.claude/projects/p/conv4.jsonl",
                "connector_name": "claude",
                "embeddings": [_SAME_CONTENT_VECTOR],
            },
        ),
        embedding_dim=4,
    )

    suggestions = find_near_duplicates(Path("unused"), connection=con, similarity_threshold=0.5)

    assert suggestions == ()


# ---------------------------------------------------------------------------
# Threshold boundary
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_find_near_duplicates_includes_pair_exactly_at_threshold() -> None:
    con = duckdb.connect(":memory:")
    _seed_connection(
        con,
        conversations=(
            {
                "conversation_id": "a",
                "title": "A",
                "file_path": "/a.jsonl",
                "connector_name": "claude",
                "embeddings": [[1.0, 0.0]],
            },
            {
                "conversation_id": "b",
                "title": "B",
                "file_path": "/b.jsonl",
                "connector_name": "codex",
                "embeddings": [[0.6, 0.8]],
            },
        ),
        embedding_dim=2,
    )

    suggestions = find_near_duplicates(Path("unused"), connection=con, similarity_threshold=0.6)

    assert len(suggestions) == 1
    assert suggestions[0].similarity == pytest.approx(0.6)


@pytest.mark.unit
def test_find_near_duplicates_excludes_pair_just_below_threshold() -> None:
    con = duckdb.connect(":memory:")
    _seed_connection(
        con,
        conversations=(
            {
                "conversation_id": "a",
                "title": "A",
                "file_path": "/a.jsonl",
                "connector_name": "claude",
                "embeddings": [[1.0, 0.0]],
            },
            {
                "conversation_id": "b",
                "title": "B",
                "file_path": "/b.jsonl",
                "connector_name": "codex",
                "embeddings": [[0.6, 0.8]],
            },
        ),
        embedding_dim=2,
    )

    suggestions = find_near_duplicates(Path("unused"), connection=con, similarity_threshold=0.61)

    assert suggestions == ()


# ---------------------------------------------------------------------------
# Connection modes and edge cases
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_find_near_duplicates_returns_empty_tuple_when_db_path_missing(tmp_path: Path) -> None:
    missing = tmp_path / "no-such.duckdb"
    assert find_near_duplicates(missing) == ()


@pytest.mark.unit
def test_find_near_duplicates_opens_own_readonly_connection_when_none_given(tmp_path: Path) -> None:
    db_path = tmp_path / "standalone.duckdb"
    _build_fixture_db(
        db_path,
        conversations=(
            {
                "conversation_id": "claude-conv-5",
                "title": "Same session",
                "file_path": "/home/user/.claude/projects/p/conv5.jsonl",
                "connector_name": "claude",
                "embeddings": [_SAME_CONTENT_VECTOR],
            },
            {
                "conversation_id": "codex-conv-5",
                "title": "Same session",
                "file_path": "/home/user/.codex/sessions/conv5.jsonl",
                "connector_name": "codex",
                "embeddings": [_SAME_CONTENT_VECTOR],
            },
        ),
        embedding_dim=4,
    )

    suggestions = find_near_duplicates(db_path, similarity_threshold=0.92)

    assert len(suggestions) == 1
    assert suggestions[0].similarity == pytest.approx(1.0)


@pytest.mark.unit
def test_find_near_duplicates_uses_default_threshold_constant_when_unspecified() -> None:
    con = duckdb.connect(":memory:")
    _seed_connection(
        con,
        conversations=(
            {
                "conversation_id": "a",
                "title": "A",
                "file_path": "/a.jsonl",
                "connector_name": "claude",
                "embeddings": [_SAME_CONTENT_VECTOR],
            },
            {
                "conversation_id": "b",
                "title": "B",
                "file_path": "/b.jsonl",
                "connector_name": "codex",
                "embeddings": [_SAME_CONTENT_VECTOR],
            },
        ),
        embedding_dim=4,
    )

    suggestions = find_near_duplicates(Path("unused"), connection=con)

    assert DEFAULT_SIMILARITY_THRESHOLD == pytest.approx(0.92)
    assert len(suggestions) == 1


@pytest.mark.unit
def test_find_near_duplicates_excludes_conversations_without_embeddings() -> None:
    """A conversation with no indexed exchanges yet has nothing to compare
    against and must never crash the comparison."""
    con = duckdb.connect(":memory:")
    _seed_connection(
        con,
        conversations=(
            {
                "conversation_id": "claude-conv-6",
                "title": "Not yet embedded",
                "file_path": "/home/user/.claude/projects/p/conv6.jsonl",
                "connector_name": "claude",
                "embeddings": [],
            },
            {
                "conversation_id": "codex-conv-6",
                "title": "Not yet embedded",
                "file_path": "/home/user/.codex/sessions/conv6.jsonl",
                "connector_name": "codex",
                "embeddings": [_SAME_CONTENT_VECTOR],
            },
        ),
        embedding_dim=4,
    )

    suggestions = find_near_duplicates(Path("unused"), connection=con, similarity_threshold=0.5)

    assert suggestions == ()


@pytest.mark.unit
def test_find_near_duplicates_falls_back_to_detect_connector_for_null_connector_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rows written before `connector_name` was threaded through
    `source_file_state` (null/empty) are routed via `detect_connector`, the
    same fallback `disk_accounting.py` uses."""
    from types import SimpleNamespace

    def fake_detect_connector(path: Path):
        if path.suffix == ".jsonl" and ".codex" in path.parts:
            return SimpleNamespace(name="codex")
        raise ValueError(f"No connector found for {path}")

    monkeypatch.setattr(
        "searchat.services.dedup_detection.detect_connector", fake_detect_connector
    )

    con = duckdb.connect(":memory:")
    _seed_connection(
        con,
        conversations=(
            {
                "conversation_id": "claude-conv-7",
                "title": "Null connector_name row",
                "file_path": "/home/user/.claude/projects/p/conv7.jsonl",
                "connector_name": "claude",
                "embeddings": [_SAME_CONTENT_VECTOR],
            },
            {
                "conversation_id": "codex-conv-7",
                "title": "Null connector_name row",
                "file_path": "/home/user/.codex/sessions/conv7.jsonl",
                "connector_name": None,
                "embeddings": [_SAME_CONTENT_VECTOR],
            },
        ),
        embedding_dim=4,
    )

    suggestions = find_near_duplicates(Path("unused"), connection=con, similarity_threshold=0.92)

    assert len(suggestions) == 1
    assert {suggestions[0].connector_a, suggestions[0].connector_b} == {"claude", "codex"}


@pytest.mark.unit
def test_find_near_duplicates_sorts_suggestions_by_similarity_descending() -> None:
    con = duckdb.connect(":memory:")
    _seed_connection(
        con,
        conversations=(
            {
                "conversation_id": "claude-1",
                "title": "T1",
                "file_path": "/c1.jsonl",
                "connector_name": "claude",
                "embeddings": [[1.0, 0.0, 0.0]],
            },
            {
                "conversation_id": "codex-1",
                "title": "T1",
                "file_path": "/x1.jsonl",
                "connector_name": "codex",
                "embeddings": [[1.0, 0.0, 0.0]],
            },
            {
                "conversation_id": "claude-2",
                "title": "T2",
                "file_path": "/c2.jsonl",
                "connector_name": "claude",
                "embeddings": [[0.0, 1.0, 0.0]],
            },
            {
                "conversation_id": "codex-2",
                "title": "T2",
                "file_path": "/x2.jsonl",
                "connector_name": "codex",
                "embeddings": [[0.1, 0.9, 0.0]],
            },
        ),
        embedding_dim=3,
    )

    suggestions = find_near_duplicates(Path("unused"), connection=con, similarity_threshold=0.5)

    assert len(suggestions) == 2
    assert suggestions[0].similarity >= suggestions[1].similarity
    assert suggestions[0].similarity == pytest.approx(1.0)


@pytest.mark.unit
def test_duplicate_suggestion_to_dict_roundtrips_all_fields() -> None:
    suggestion = DuplicateSuggestion(
        conversation_id_a="a",
        connector_a="claude",
        title_a="Title A",
        conversation_id_b="b",
        connector_b="codex",
        title_b="Title B",
        similarity=0.97,
    )

    assert suggestion.to_dict() == {
        "conversation_id_a": "a",
        "connector_a": "claude",
        "title_a": "Title A",
        "conversation_id_b": "b",
        "connector_b": "codex",
        "title_b": "Title B",
        "similarity": 0.97,
    }
