"""CLI command: searchat migrate-storage

Migration from v1 (Parquet+FAISS) to v2 (DuckDB) is complete.
This command is retained for backward compatibility but no longer performs migration.
"""
from __future__ import annotations


def run_migrate_storage(argv: list[str]) -> int:
    """Entry point for `searchat migrate-storage`."""
    from rich.console import Console

    console = Console()

    if "-h" in set(argv) or "--help" in set(argv):
        _print_help()
        return 0

    console.print(
        "[green]Migration complete.[/green] "
        "Searchat v0.7.0 uses DuckDB as the sole storage backend.\n"
        "The migrate-storage command is no longer needed."
    )
    return 0


def _print_help() -> None:
    print("Usage: searchat migrate-storage [OPTIONS]")
    print()
    print("v1→v2 migration is complete. DuckDB is now the sole storage backend.")
    print("This command is retained for backward compatibility.")
