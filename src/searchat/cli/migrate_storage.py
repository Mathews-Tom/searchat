"""CLI command: searchat migrate-storage

Flags:
    --dry-run   Scan existing data, estimate migration scope, no modification
    --verify    Compare row counts between v1 (Parquet) and v2 (DuckDB)
    --rollback  Disable DuckDB backend in config (set storage.backend = "parquet")
"""
from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.table import Table

from searchat.config import Config, PathResolver


def run_migrate_storage(argv: list[str]) -> int:
    """Entry point for `searchat migrate-storage`."""
    console = Console()
    flags = set(argv)

    if "-h" in flags or "--help" in flags:
        _print_help()
        return 0

    config = Config.load()
    search_dir = Path(PathResolver.get_shared_search_dir(config))
    duckdb_path = config.storage.resolve_duckdb_path(search_dir)

    if "--dry-run" in flags:
        return _dry_run(console, search_dir, duckdb_path)

    if "--verify" in flags:
        return _verify(console, search_dir, duckdb_path)

    if "--rollback" in flags:
        return _rollback(console)

    return _migrate(console, search_dir, duckdb_path, config)


def _dry_run(console: Console, search_dir: Path, duckdb_path: Path) -> int:
    from searchat.storage.migration_v1_to_v2 import dry_run

    console.print("[bold]Dry run — scanning existing v1 data...[/bold]\n")
    report = dry_run(search_dir, duckdb_path)

    table = Table(title="Migration Estimate")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", justify="right")

    for key, val in report.to_dict().items():
        table.add_row(key, str(val))

    console.print(table)
    console.print("\n[dim]No data was modified. Run without --dry-run to migrate.[/dim]")
    return 0


def _verify(console: Console, search_dir: Path, duckdb_path: Path) -> int:
    from searchat.storage.migration_v1_to_v2 import verify

    if not duckdb_path.exists():
        console.print(f"[red]DuckDB file not found: {duckdb_path}[/red]")
        console.print("[dim]Run `searchat migrate-storage` first.[/dim]")
        return 1

    console.print("[bold]Verifying v1 ↔ v2 row counts...[/bold]\n")
    result = verify(search_dir, duckdb_path)

    table = Table(title="Row Count Comparison")
    table.add_column("Table", style="cyan")
    table.add_column("v1 (Parquet)", justify="right")
    table.add_column("v2 (DuckDB)", justify="right")
    table.add_column("Match", justify="center")

    all_match = True
    for tbl_name, counts in result.items():
        v1 = counts["v1"]
        v2 = counts["v2"]
        # Exchanges and embeddings have no v1 equivalent — skip match check
        if tbl_name in ("exchanges", "verbatim_embeddings"):
            match_str = "[dim]n/a[/dim]"
        elif v1 == v2:
            match_str = "[green]yes[/green]"
        else:
            match_str = "[red]NO[/red]"
            all_match = False
        table.add_row(tbl_name, str(v1), str(v2), match_str)

    console.print(table)

    if all_match:
        console.print("\n[green]All comparable row counts match.[/green]")
        return 0
    console.print("\n[yellow]Row count mismatches detected.[/yellow]")
    return 1


def _migrate(console: Console, search_dir: Path, duckdb_path: Path, config: Config) -> int:
    from searchat.storage.migration_v1_to_v2 import migrate

    if duckdb_path.exists():
        console.print(f"[yellow]DuckDB file already exists: {duckdb_path}[/yellow]")
        console.print("[dim]Delete it manually to re-run migration, or use --verify.[/dim]")
        return 1

    console.print(f"[bold]Migrating v1 → v2...[/bold]")
    console.print(f"  Source: {search_dir / 'data'}")
    console.print(f"  Target: {duckdb_path}\n")

    stats = migrate(
        search_dir,
        duckdb_path,
        memory_limit_mb=config.performance.memory_limit_mb,
    )

    table = Table(title="Migration Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", justify="right")

    for key, val in stats.to_dict().items():
        if key != "errors":
            table.add_row(key, str(val))

    console.print(table)

    if stats.errors:
        console.print("\n[red]Errors:[/red]")
        for err in stats.errors:
            console.print(f"  [red]{err}[/red]")
        return 1

    console.print(f"\n[green]Migration complete in {stats.elapsed_seconds:.1f}s.[/green]")
    console.print("[dim]Run `searchat migrate-storage --verify` to validate.[/dim]")
    return 0


def _rollback(console: Console) -> int:
    """Set storage.backend to 'parquet' in user config."""
    from searchat.config.constants import DEFAULT_DATA_DIR, DEFAULT_CONFIG_SUBDIR, SETTINGS_FILE

    config_path = DEFAULT_DATA_DIR / DEFAULT_CONFIG_SUBDIR / SETTINGS_FILE

    if not config_path.exists():
        console.print("[yellow]No user config file found. Nothing to rollback.[/yellow]")
        return 0

    content = config_path.read_text(encoding="utf-8")

    # Check current backend
    import re
    match = re.search(r'backend\s*=\s*"(\w+)"', content)
    current_backend = match.group(1) if match else "parquet"

    if current_backend == "parquet":
        console.print("[dim]Storage backend is already 'parquet'.[/dim]")
        return 0

    # Replace the backend value in the TOML file
    new_content = re.sub(
        r'(backend\s*=\s*)"[^"]*"',
        r'\1"parquet"',
        content,
    )
    config_path.write_text(new_content, encoding="utf-8")

    console.print(f"[green]Rolled back storage.backend from '{current_backend}' to 'parquet'.[/green]")
    return 0


def _print_help() -> None:
    print("Usage: searchat migrate-storage [OPTIONS]")
    print()
    print("Migrate v1 (Parquet+FAISS) data to v2 (DuckDB) storage.")
    print()
    print("Options:")
    print("  --dry-run   Scan and estimate, no modification")
    print("  --verify    Compare row counts between v1 and v2")
    print("  --rollback  Set storage.backend to 'parquet' in config")
    print("  -h, --help  Show this help message")
