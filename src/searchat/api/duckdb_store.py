"""Compatibility shim — IndexStatistics moved to unified_storage."""

from searchat.storage.unified_storage import IndexStatistics, UnifiedStorage as DuckDBStore

__all__ = ["DuckDBStore", "IndexStatistics"]
