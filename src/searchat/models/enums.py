"""Enumerations for searchat."""
from __future__ import annotations

from enum import Enum


class SearchMode(Enum):
    """Search mode for querying conversations."""
    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"
