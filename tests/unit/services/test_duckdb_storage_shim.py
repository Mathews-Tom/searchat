from searchat.api.duckdb_store import DuckDBStore as ApiDuckDBStore
from searchat.api.duckdb_store import IndexStatistics as ApiIndexStatistics
from searchat.services.duckdb_storage import DuckDBStore, IndexStatistics


def test_api_duckdb_store_shim_reexports_service_symbols() -> None:
    assert ApiDuckDBStore is DuckDBStore
    assert ApiIndexStatistics is IndexStatistics
