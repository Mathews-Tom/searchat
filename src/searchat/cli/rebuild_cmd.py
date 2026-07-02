"""CLI commands: searchat rebuild-derived / searchat reingest-sources.

rebuild-derived rebuilds exchange/FTS/HNSW indexes from already-indexed
conversation data. It never opens a source connector file and is always
safe to run — including with zero source files present.

reingest-sources re-ingests from source JSONL/session files, replacing the
existing legacy Parquet+FAISS index. It stays guarded exactly as before:
refuses with RuntimeError unless an existing index is absent or --force is
passed. For safe maintenance (restoring indexes after a compaction, backup
restore, or corruption), use rebuild-derived instead.
"""
from __future__ import annotations

import argparse
import sys


def run_rebuild_derived(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="searchat rebuild-derived",
        description=(
            "Rebuild exchange, FTS keyword, and HNSW vector indexes from "
            "already-indexed conversations. Reads only from the local "
            "database — never opens a source conversation file. Always "
            "safe to run, including with no source files present."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Wipe and regenerate exchanges/embeddings for every conversation "
            "and rebuild the FTS/HNSW indexes from scratch, instead of only "
            "completing conversations that are missing exchanges. Still "
            "never touches source files — always safe."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of a summary.")
    args = parser.parse_args(argv)

    from searchat.config import Config, PathResolver
    from searchat.core.unified_indexer import UnifiedIndexer
    from searchat.services.storage_service import build_storage_service

    config = Config.load()
    search_dir = PathResolver.get_shared_search_dir(config)

    try:
        storage = build_storage_service(search_dir, config=config, read_only=False)
        indexer = UnifiedIndexer(search_dir, config, storage=storage)
        stats = indexer.rebuild_derived(force=args.force)
    except Exception as exc:
        print(f"Error: failed to rebuild derived data: {exc}", file=sys.stderr)
        return 1

    if args.json:
        import json as json_module

        print(json_module.dumps(
            {
                "conversations_processed": stats.conversations_processed,
                "exchanges_rebuilt": stats.exchanges_rebuilt,
                "embeddings_rebuilt": stats.embeddings_rebuilt,
                "rebuild_time_seconds": stats.rebuild_time_seconds,
                "forced": stats.forced,
            },
            indent=2,
        ))
        return 0

    from rich.console import Console

    console = Console()
    console.print("[bold green]Rebuild complete[/bold green]")
    console.print(f"  Conversations processed: {stats.conversations_processed}")
    console.print(f"  Exchanges rebuilt:        {stats.exchanges_rebuilt}")
    console.print(f"  Embeddings rebuilt:       {stats.embeddings_rebuilt}")
    console.print(f"  Forced full rebuild:      {stats.forced}")
    console.print(f"  Time:                     {stats.rebuild_time_seconds:.2f}s")
    return 0


def run_reingest_sources(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="searchat reingest-sources",
        description=(
            "Re-ingest conversations from source JSONL/session files, "
            "replacing the existing index. DANGEROUS: if source files are "
            "missing or incomplete, indexed conversations absent from "
            "current source files are lost. Guarded — refuses with a "
            "RuntimeError unless --force is passed and you have verified "
            "complete source files. For safe maintenance (restoring "
            "indexes after a compaction or backup restore), use "
            "`searchat rebuild-derived` instead — it never touches source "
            "files."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Required to proceed when an existing index is detected.",
    )
    args = parser.parse_args(argv)

    from searchat.config import Config, PathResolver
    from searchat.core.indexer import ConversationIndexer

    config = Config.load()
    search_dir = PathResolver.get_shared_search_dir(config)
    indexer = ConversationIndexer(search_dir, config)

    try:
        stats = indexer.index_all(force=args.force)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("Reingest complete.")
    print(f"  Conversations: {stats.total_conversations}")
    print(f"  Messages:      {stats.total_messages}")
    print(f"  Time:          {stats.index_time_seconds:.2f}s")
    return 0
