"""CLI command: searchat doctor — read-only storage diagnostics report."""
from __future__ import annotations

import argparse
import json
import sys


def _format_bytes(num_bytes: int | float) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1024.0:
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} PB"


def _format_age(seconds: float | None) -> str:
    if seconds is None:
        return "never"
    if seconds < 60:
        return f"{seconds:.0f}s ago"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.0f}m ago"
    hours = minutes / 60
    if hours < 24:
        return f"{hours:.1f}h ago"
    return f"{hours / 24:.1f}d ago"


def _bloat_style(ratio: float) -> str:
    if ratio >= 3.0:
        return "red"
    if ratio >= 1.5:
        return "yellow"
    return "green"


def run_doctor(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="searchat doctor",
        description=(
            "Read-only storage diagnostics: DuckDB bloat ratio, per-backup redundancy, "
            "per-harness source sizes, WAL size, and last-backup age. Never mutates data."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of tables.")
    args = parser.parse_args(argv)

    from searchat.config import Config, PathResolver
    from searchat.services.storage_health import build_storage_doctor_report

    config = Config.load()
    search_dir = PathResolver.get_shared_search_dir(config)

    try:
        report = build_storage_doctor_report(search_dir, config)
    except Exception as exc:
        print(f"Error: failed to build storage doctor report: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
        return 0

    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()
    console.print(Panel(f"[bold]Storage Doctor[/bold]\n{search_dir}", expand=False))

    if not report.db_exists:
        console.print("[yellow]No DuckDB index found yet — nothing to diagnose.[/yellow]")
    else:
        overview = Table(show_header=True, header_style="bold", title="Database")
        overview.add_column("Metric")
        overview.add_column("Value")
        overview.add_row("On-disk size", _format_bytes(report.total_bytes))
        overview.add_row("Live data (estimated)", _format_bytes(report.live_bytes))
        overview.add_row("WAL size", _format_bytes(report.wal_bytes))
        style = _bloat_style(report.bloat_ratio)
        overview.add_row("Bloat ratio", f"[{style}]{report.bloat_ratio:.2f}x[/{style}]")
        console.print(overview)

    console.print(f"\nLast backup: {_format_age(report.last_backup_age_seconds)}")

    if report.backups:
        backups_table = Table(show_header=True, header_style="bold", title="\nBackups")
        backups_table.add_column("Name")
        backups_table.add_column("Files", justify="right")
        backups_table.add_column("Size", justify="right")
        backups_table.add_column("Redundant")
        for backup in report.backups:
            redundant_str = "[green]yes[/green]" if backup.redundant else "no"
            backups_table.add_row(
                backup.backup_name,
                str(backup.file_count),
                _format_bytes(backup.total_size_bytes),
                redundant_str,
            )
        console.print(backups_table)
    else:
        console.print("\n[dim]No backups found.[/dim]")

    if report.harness_sources:
        harness_table = Table(show_header=True, header_style="bold", title="\nHarness Sources")
        harness_table.add_column("Connector")
        harness_table.add_column("Files", justify="right")
        harness_table.add_column("Size", justify="right")
        for harness in sorted(report.harness_sources, key=lambda h: h.total_size_bytes, reverse=True):
            harness_table.add_row(
                harness.connector, str(harness.file_count), _format_bytes(harness.total_size_bytes)
            )
        console.print(harness_table)
    else:
        console.print("\n[dim]No harness sources discovered.[/dim]")

    redundant_count = sum(1 for backup in report.backups if backup.redundant)
    if redundant_count:
        console.print(
            f"\n[yellow]{redundant_count} backup(s) are fully redundant with live data "
            "and may be safe to delete.[/yellow]"
        )

    return 0
