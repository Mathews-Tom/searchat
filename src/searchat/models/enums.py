"""Enumerations for searchat."""
from enum import Enum


class SearchMode(Enum):
    """Search mode for querying conversations."""
    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"
