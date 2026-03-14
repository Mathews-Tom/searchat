"""Compatibility shim for the DuckDB-backed storage service."""

from searchat.services.duckdb_storage import DuckDBStore, IndexStatistics

__all__ = ["DuckDBStore", "IndexStatistics"]
