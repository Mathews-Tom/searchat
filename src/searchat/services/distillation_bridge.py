"""Tiered memory: distill-old, keep-hot (M9).

The missing integration seam (enhancement-analysis Gap 2) between
``storage/unified_storage.py`` -- the v2 unified store's ``conversations``/
``messages`` source-of-truth tables plus its derived ``exchanges``/
``verbatim_embeddings`` hot FTS/HNSW index -- and ``palace/distiller.py``'s
``Distiller``, which today runs against its own separate ``PalaceStorage``
(``palace.duckdb``) + FAISS index and has never read from or written back
to ``UnifiedStorage``.

This PR lands the first step of the per-conversation pipeline:

1. ``select_distillation_candidates`` -- conversations older than a
   configurable age threshold that still have at least one hot exchange
   row. Palace-independent: reads only ``UnifiedStorage``, no faiss/
   rank-bm25 import. Already-distilled-and-evicted conversations drop out
   of candidacy on their own (no exchange rows left), so this is
   naturally idempotent across repeated runs.

Distillate generation (``generate_distillate``), hot-index eviction
(``evict_hot_rows``), the promotion path (``rehydrate_verbatim``), and the
``run_tiering_cycle`` orchestrator land in later commits/PRs of this stack.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from searchat.storage.unified_storage import UnifiedStorage

# ---------------------------------------------------------------------------
# 1. Candidate selection (palace-independent)
# ---------------------------------------------------------------------------


def select_distillation_candidates(
    storage: UnifiedStorage,
    *,
    age_threshold_days: int,
    now: datetime | None = None,
) -> list[str]:
    """Conversation ids eligible for distillation: `updated_at` older than
    `age_threshold_days` AND still present in the hot index (at least one
    `exchanges` row). Already-evicted conversations are structurally
    excluded -- they have zero exchange rows -- making repeated calls
    naturally idempotent without consulting palace state at all.
    """
    now = now or datetime.now()
    cutoff = now - timedelta(days=age_threshold_days)
    cur = storage.connection.cursor()
    try:
        rows = cur.execute(
            "SELECT DISTINCT c.conversation_id FROM conversations c "
            "JOIN exchanges e ON e.conversation_id = c.conversation_id "
            "WHERE c.updated_at < ? "
            "ORDER BY c.conversation_id",
            [cutoff],
        ).fetchall()
        return [row[0] for row in rows]
    finally:
        cur.close()
