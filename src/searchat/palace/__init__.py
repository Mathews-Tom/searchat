"""Memory palace distillation system for conversation memory.

Lazily re-exports its submodules' public symbols via module `__getattr__`
(PEP 562) instead of importing them eagerly. `distiller.py` and
`faiss_index.py` need the `palace` extra's `faiss-cpu`; `bm25_index.py`
(via `query.py`) needs `rank-bm25`. Importing this package -- or any of
its submodules that do NOT themselves need those (`storage.py`, `llm.py`)
-- must not require either dependency to be installed; only actually
touching a symbol that needs one does.
"""
from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from searchat.palace.distiller import Distiller
    from searchat.palace.faiss_index import DistilledFaissIndex
    from searchat.palace.llm import (
        CLIDistillationLLM,
        DistillationInput,
        DistillationLLM,
        DistillationOutput,
    )
    from searchat.palace.query import PalaceQuery
    from searchat.palace.storage import PalaceStorage

__all__ = [
    "DistillationLLM",
    "CLIDistillationLLM",
    "DistillationInput",
    "DistillationOutput",
    "PalaceStorage",
    "DistilledFaissIndex",
    "Distiller",
    "PalaceQuery",
]

_ATTR_MODULES = {
    "DistillationLLM": "searchat.palace.llm",
    "CLIDistillationLLM": "searchat.palace.llm",
    "DistillationInput": "searchat.palace.llm",
    "DistillationOutput": "searchat.palace.llm",
    "PalaceStorage": "searchat.palace.storage",
    "DistilledFaissIndex": "searchat.palace.faiss_index",
    "Distiller": "searchat.palace.distiller",
    "PalaceQuery": "searchat.palace.query",
}


def __getattr__(name: str) -> object:
    module_name = _ATTR_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(importlib.import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(__all__)
