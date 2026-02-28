"""CLI command: searchat prune — prune stale expertise records."""
from __future__ import annotations

import argparse

from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm


def run_prune(argv: list[str]) -> int:
    """Entry point for `searchat prune`."""
    parser = argparse.ArgumentParser(
        prog="searchat prune",
        description="Prune stale expertise records from the knowledge store.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Staleness threshold 0.0-1.0 (default: from config)",
    )
    parser.add_argument("--domain", default=None, help="Filter to a specific domain")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Show what would be pruned without deleting (default: True)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Execute pruning without confirmation prompt",
    )
    args = parser.parse_args(argv)

    # --force implies not dry-run
    dry_run = args.dry_run and not args.force

    console = Console()

    from searchat.config import Config, PathResolver
    from searchat.expertise.store import ExpertiseStore
    from searchat.expertise.staleness import StalenessManager

    config = Config.load()
    if not config.expertise.enabled:
        console.print("[red]Expertise store is disabled in config.[/red]")
        return 1

    search_dir = PathResolver.get_shared_search_dir(config)
    store = ExpertiseStore(search_dir)
    manager = StalenessManager(store, config)

    threshold = args.threshold if args.threshold is not None else config.expertise.staleness_threshold

    # Preview stale records first
    stale_pairs = manager.get_stale_records(threshold=threshold)
    if args.domain:
        stale_pairs = [(r, s) for r, s in stale_pairs if r.domain == args.domain]

    if not stale_pairs:
        console.print(f"[green]No stale records found above threshold {threshold:.2f}[/green]")
        return 0

    table = Table(title=f"Stale Records (threshold={threshold:.2f})", show_lines=False)
    table.add_column("ID", style="dim", no_wrap=True, max_width=20)
    table.add_column("Type", style="cyan")
    table.add_column("Domain", style="magenta")
    table.add_column("Staleness", style="red", justify="right")
    table.add_column("Days Since Validated", justify="right")
    table.add_column("Content", no_wrap=False, max_width=50)

    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    for record, score in sorted(stale_pairs, key=lambda t: t[1], reverse=True):
        lv = record.last_validated
        if lv.tzinfo is None:
            lv = lv.replace(tzinfo=timezone.utc)
        days = int((now - lv).total_seconds() / 86400)
        table.add_row(
            record.id[:16] + "…" if len(record.id) > 16 else record.id,
            record.type.value,
            record.domain,
            f"{score:.3f}",
            str(days),
            record.content[:80] + ("…" if len(record.content) > 80 else ""),
        )

    console.print(table)
    console.print(f"\n[bold]{len(stale_pairs)}[/bold] records would be pruned.")

    if dry_run:
        console.print("[yellow]Dry-run mode — no changes made. Use --force to execute.[/yellow]")
        console.print(f"\nSummary: Pruned 0 records, skipped 0 (dry_run=True)")
        return 0

    if not args.force:
        confirmed = Confirm.ask(f"Prune {len(stale_pairs)} records?", default=False)
        if not confirmed:
            console.print("[yellow]Aborted.[/yellow]")
            return 0

    result = manager.prune(threshold=args.threshold, dry_run=False)

    pruned = len(result.pruned)
    skipped = len(result.skipped)
    console.print(f"\n[bold green]Pruning complete[/bold green]")
    console.print(f"Summary: Pruned {pruned} records, skipped {skipped} (dry_run=False)")
    return 0
