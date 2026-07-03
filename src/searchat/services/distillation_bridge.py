"""Tiered memory: distill-old, keep-hot (M9).

The missing integration seam (enhancement-analysis Gap 2) between
``storage/unified_storage.py`` -- the v2 unified store's ``conversations``/
``messages`` source-of-truth tables plus its derived ``exchanges``/
``verbatim_embeddings`` hot FTS/HNSW index -- and ``palace/distiller.py``'s
``Distiller``, which today runs against its own separate ``PalaceStorage``
(``palace.duckdb``) + FAISS index and has never read from or written back
to ``UnifiedStorage``.

This PR lands the first two steps of the per-conversation pipeline:

1. ``select_distillation_candidates`` -- conversations older than a
   configurable age threshold that still have at least one hot exchange
   row. Palace-independent: reads only ``UnifiedStorage``, no faiss/
   rank-bm25 import. Already-distilled-and-evicted conversations drop out
   of candidacy on their own (no exchange rows left), so this is
   naturally idempotent across repeated runs.
2. ``generate_distillate`` -- invokes the palace ``Distiller`` for one
   conversation via ``_UnifiedStorageDuckStore``, an adapter translating
   ``UnifiedStorage``'s actual read methods into the
   ``get_conversation``/``get_conversation_messages`` shape
   ``Distiller._read_conversation`` expects.

Hot-index eviction (``evict_hot_rows``), the promotion path
(``rehydrate_verbatim``), and the ``run_tiering_cycle`` orchestrator land
in later commits/PRs of this stack.

Graceful degradation: importing this module never touches the `palace`
extra (faiss-cpu, rank-bm25). ``select_distillation_candidates`` needs
only DuckDB and never raises for a missing extra. Only
``generate_distillate`` needs palace, and raises ``PalaceUnavailableError``
-- never a bare ``ImportError`` -- when it is not installed.
"""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from searchat.config.settings import Config
from searchat.storage.unified_storage import UnifiedStorage

if TYPE_CHECKING:
    from searchat.palace.distiller import Distiller
    from searchat.palace.llm import DistillationLLM
    from searchat.palace.storage import PalaceStorage


class PalaceUnavailableError(RuntimeError):
    """Raised when a distillation-bridge operation needs the `palace`
    extra (faiss-cpu, rank-bm25) but it is not installed.

    Callers should treat this as "feature disabled", not a crash:
    candidate selection never raises it (it needs only DuckDB). Only
    distillate generation does.
    """


def _importable(module_name: str) -> bool:
    """True if `module_name` can be imported, without actually importing
    it. Checks `sys.modules` first: a module already present there (even
    a test double substituted via `sys.modules[name] = ...`) is treated as
    importable without touching `importlib.util.find_spec`, which raises
    `ValueError` for a `unittest.mock.MagicMock` standing in for a module
    (its `__spec__` dunder is unset, unlike a real module's).
    """
    if module_name in sys.modules:
        return sys.modules[module_name] is not None
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ValueError):
        return False


def palace_available() -> bool:
    """True if the runtime dependency distillate generation actually needs
    (`faiss`, via `palace.distiller.Distiller`'s FAISS index) is importable.

    Deliberately narrower than "the whole `palace` extra": `rank-bm25` is
    only used by `palace.query.PalaceQuery`'s keyword search (a different
    code path in `core/unified_search.py`, unrelated to this bridge), so
    its absence must not block distillation/eviction/rehydration -- doing
    so would over-degrade a feature that doesn't actually need it. Cheap
    existence check -- does not actually import `faiss`.
    """
    return _importable("faiss")


def _import_palace() -> tuple[type["Distiller"], type["PalaceStorage"]]:
    """Import `Distiller` + `PalaceStorage`, raising `PalaceUnavailableError`
    -- not a bare `ImportError` that would propagate out of an unrelated
    call site -- when the `palace` extra isn't installed."""
    try:
        from searchat.palace.distiller import Distiller
        from searchat.palace.storage import PalaceStorage
    except ImportError as exc:
        raise PalaceUnavailableError(
            "distillation requires the 'palace' extra (faiss-cpu, rank-bm25): "
            "install with `uv sync --extra palace`"
        ) from exc
    return Distiller, PalaceStorage


class _UnifiedStorageDuckStore:
    """Adapts `UnifiedStorage` to the duck-typed `get_conversation` /
    `get_conversation_messages` store `Distiller._read_conversation`
    expects -- the missing read-side half of the integration seam (Gap 2):
    the two storages' method names never matched, so `Distiller` could
    never actually read a v2-indexed conversation before this adapter.
    """

    def __init__(self, storage: UnifiedStorage) -> None:
        self._storage = storage

    def get_conversation(self, conversation_id: str) -> dict | None:
        return self._storage.get_conversation_meta(conversation_id)

    def get_conversation_messages(self, conversation_id: str) -> list[dict]:
        record = self._storage.get_conversation_record(conversation_id)
        return list(record["messages"]) if record else []


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


# ---------------------------------------------------------------------------
# 2. Distillate generation (needs the palace extra)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DistillateResult:
    """Outcome of `generate_distillate` for one conversation."""

    conversation_id: str
    objects_created: int
    has_distillate: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "conversation_id": self.conversation_id,
            "objects_created": self.objects_created,
            "has_distillate": self.has_distillate,
        }


def generate_distillate(
    storage: UnifiedStorage,
    *,
    conversation_id: str,
    config: Config,
    llm: "DistillationLLM",
    search_dir: Path,
    embedder: object | None = None,
    palace_storage: "PalaceStorage | None" = None,
) -> DistillateResult:
    """Invoke the palace `Distiller` for one conversation, reading it
    through `_UnifiedStorageDuckStore` and persisting the distillate to
    `palace_storage` (or a freshly opened one under `search_dir/data` when
    not supplied). Raises `PalaceUnavailableError` if the `palace` extra
    is not installed.

    `has_distillate` is true whenever `conversation_id` has ANY persisted
    distillate object afterward -- including one from a prior call --
    distinguishing "nothing new to distill because it's already fully
    distilled" from "nothing distilled because every exchange was too
    short" (`Distiller` marks the latter `no_valid_exchanges` and creates
    no objects at all). Callers must not evict on `has_distillate=False`:
    that conversation has no distillate to fall back on.
    """
    Distiller, PalaceStorageCls = _import_palace()

    owns_storage = palace_storage is None
    resolved_storage: "PalaceStorage" = (
        palace_storage if palace_storage is not None else PalaceStorageCls(search_dir / "data")
    )
    distiller = Distiller(
        search_dir=search_dir,
        config=config,
        llm=llm,
        duckdb_store=_UnifiedStorageDuckStore(storage),
        embedder=embedder,
        palace_storage=resolved_storage,
    )
    try:
        objects = distiller.distill_conversation(conversation_id)
        has_distillate = conversation_id in resolved_storage.get_distilled_conversation_ids()
        return DistillateResult(
            conversation_id=conversation_id,
            objects_created=len(objects),
            has_distillate=has_distillate,
        )
    finally:
        if owns_storage:
            resolved_storage.close()
