"""CLI command: searchat extract — run expertise extraction on indexed conversations."""
from __future__ import annotations

import argparse

from rich.console import Console


def run_extract(argv: list[str]) -> int:
    """Entry point for `searchat extract`."""
    parser = argparse.ArgumentParser(
        prog="searchat extract",
        description="Extract expertise records from indexed conversations.",
    )
    parser.add_argument(
        "--mode",
        choices=["heuristic_only", "full", "llm_only"],
        default="heuristic_only",
        help="Extraction mode (default: heuristic_only)",
    )
    parser.add_argument("--project", default=None, help="Filter by project")
    parser.add_argument("--domain", default="general", help="Default domain for records")
    parser.add_argument("--limit", type=int, default=0, help="Max conversations to process (0 = all)")
    args = parser.parse_args(argv)

    console = Console()

    from searchat.config import Config, PathResolver
    from searchat.expertise.pipeline import create_pipeline

    config = Config.load()
    if not config.expertise.enabled:
        console.print("[red]Expertise store is disabled in config.[/red]")
        return 1

    search_dir = PathResolver.get_shared_search_dir(config)
    pipeline = create_pipeline(config, search_dir)

    console.print(f"[bold]Extracting expertise[/bold] (mode={args.mode})")

    from searchat.api.duckdb_store import DuckDBStore

    duckdb_store = DuckDBStore(search_dir, memory_limit_mb=config.performance.memory_limit_mb)
    conversations = duckdb_store.list_conversations(
        project_id=args.project,
        limit=args.limit if args.limit > 0 else None,
    )

    console.print(f"Processing {len(conversations)} conversations...")

    stats = pipeline.extract_batch(
        conversations,
        mode=args.mode,
        default_domain=args.domain,
    )

    console.print(f"\n[bold green]Extraction complete[/bold green]")
    console.print(f"  Conversations processed: {stats.conversations_processed}")
    console.print(f"  Records created: {stats.records_created}")
    console.print(f"  Records reinforced: {stats.records_reinforced}")
    console.print(f"  Duplicates flagged: {stats.records_flagged}")
    console.print(f"  Heuristic extractions: {stats.heuristic_extracted}")
    console.print(f"  LLM extractions: {stats.llm_extracted}")

    if stats.errors:
        console.print(f"\n[yellow]Errors ({len(stats.errors)}):[/yellow]")
        for err in stats.errors[:10]:
            console.print(f"  - {err}")

    return 0
