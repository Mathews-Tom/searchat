"""CLI command: searchat compact — verified copy-compaction of the DuckDB store.

Reclaims dead blocks left behind by append-only checkpoint churn via the
checkpoint -> attach -> COPY FROM DATABASE -> verify -> atomic-rename
sequence in services/compaction.py. Runs unconditionally when invoked --
no bloat-ratio gating, unlike the auto-trigger wired into graceful
shutdown (see services.compaction.run_auto_compact_if_needed). Isolated
in a subprocess by default so a DuckDB FATAL cannot corrupt the original
file or take down this CLI process.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from searchat.services.compaction import CompactionResult


def _format_bytes(num_bytes: int | float) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1024.0:
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} PB"


def _result_to_dict(result: "CompactionResult") -> dict[str, object]:
    verification = None
    if result.verification is not None:
        verification = {
            "passed": result.verification.passed,
            "row_counts_match": result.verification.row_counts_match,
            "index_names_match": result.verification.index_names_match,
            "fts_probe_match": result.verification.fts_probe_match,
            "vector_probe_match": result.verification.vector_probe_match,
            "symmetric_diff_match": result.verification.symmetric_diff_match,
            "mismatches": list(result.verification.mismatches),
        }
    return {
        "success": result.success,
        "original_path": str(result.original_path),
        "original_size_bytes": result.original_size_bytes,
        "compacted_size_bytes": result.compacted_size_bytes,
        "bytes_reclaimed": result.bytes_reclaimed,
        "preserved_original_path": (
            str(result.preserved_original_path) if result.preserved_original_path else None
        ),
        "verification": verification,
        "error": result.error,
        "duration_seconds": result.duration_seconds,
    }


def run_compact(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="searchat compact",
        description=(
            "Reclaim dead DuckDB blocks via verified copy-compaction. Never "
            "mutates the database until the compacted copy is proven "
            "query-identical. Runs unconditionally -- for the bloat-ratio "
            "gated check used on shutdown, see the auto-trigger."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of a summary.")
    parser.add_argument(
        "--in-process",
        action="store_true",
        help=(
            "Run compaction in this process instead of an isolated "
            "subprocess. Debugging only -- a DuckDB FATAL would take down "
            "this CLI process and skip the crash-safety guarantee."
        ),
    )
    args = parser.parse_args(argv)

    from searchat.config import Config, PathResolver
    from searchat.services.compaction import compact_database, record_compaction_completed

    config = Config.load()
    search_dir = PathResolver.get_shared_search_dir(config)
    db_path = config.storage.resolve_duckdb_path(search_dir)

    try:
        result = compact_database(db_path, subprocess_isolated=not args.in_process)
    except Exception as exc:
        print(f"Error: failed to compact database: {exc}", file=sys.stderr)
        return 1

    if result.success:
        record_compaction_completed(search_dir)

    if args.json:
        print(json.dumps(_result_to_dict(result), indent=2))
        return 0 if result.success else 1

    from rich.console import Console

    console = Console()
    if not result.success:
        console.print("[bold red]Compaction failed[/bold red]")
        console.print(f"  {result.error}")
        return 1

    console.print("[bold green]Compaction complete[/bold green]")
    console.print(f"  Original size:   {_format_bytes(result.original_size_bytes)}")
    console.print(f"  Compacted size:  {_format_bytes(result.compacted_size_bytes)}")
    console.print(f"  Bytes reclaimed: {_format_bytes(result.bytes_reclaimed)}")
    console.print(f"  Time:            {result.duration_seconds:.2f}s")
    return 0
