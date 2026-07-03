"""CLI command: searchat disk -- read-only per-agent, self, M7 cruft-advisor, and M11 dedup-suggestion disk-usage report."""

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


def _format_age(age_days: float | None) -> str:
    if age_days is None:
        return "-"
    if age_days < 1:
        return f"{age_days * 24:.0f}h"
    return f"{age_days:.0f}d"


def run_disk(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="searchat disk",
        description="Read-only per-agent and Searchat self disk-usage report.",
    )
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of tables.")
    args = parser.parse_args(argv)

    from searchat.config import Config, PathResolver
    from searchat.services.disk_accounting import build_disk_accounting_report

    config = Config.load()
    search_dir = PathResolver.get_shared_search_dir(config)

    try:
        report = build_disk_accounting_report(search_dir, config)
    except Exception as exc:
        print(f"Error: failed to build disk accounting report: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
        return 0

    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()
    console.print(Panel(f"[bold]Disk Manager[/bold]\n{search_dir}", expand=False))

    if report.agents:
        agents_table = Table(show_header=True, header_style="bold", title="Agents")
        agents_table.add_column("Connector")
        agents_table.add_column("Size", justify="right")
        agents_table.add_column("Files", justify="right")
        agents_table.add_column("Conversations", justify="right")
        agents_table.add_column("Indexed", justify="right")
        agents_table.add_column("Unindexed", justify="right")
        agents_table.add_column("Oldest", justify="right")
        agents_table.add_column("Newest", justify="right")
        for agent in report.agents:
            agents_table.add_row(
                agent.connector,
                _format_bytes(agent.total_size_bytes),
                str(agent.total_file_count),
                str(agent.conversation_file_count),
                str(agent.indexed_file_count),
                str(agent.unindexed_file_count),
                _format_age(agent.oldest_conversation_age_days),
                _format_age(agent.newest_conversation_age_days),
            )
        console.print(agents_table)
    else:
        console.print("[dim]No registered connectors discovered any files.[/dim]")

    self_usage = report.searchat_self
    self_table = Table(show_header=True, header_style="bold", title="\nSearchat Self")
    self_table.add_column("Subdirectory")
    self_table.add_column("Size", justify="right")
    self_table.add_column("Files", justify="right")
    self_table.add_column("Present", justify="center")
    for sub in self_usage.subdirectories:
        self_table.add_row(
            sub.label,
            _format_bytes(sub.total_size_bytes),
            str(sub.file_count),
            "yes" if sub.exists else "no",
        )
    console.print(self_table)
    console.print(f"\nTotal Searchat footprint: {_format_bytes(self_usage.total_size_bytes)}")

    if report.cruft_findings:
        cruft_table = Table(
            show_header=True,
            header_style="bold",
            title="\nCruft (non-conversation artifacts)",
        )
        cruft_table.add_column("Label")
        cruft_table.add_column("Size", justify="right")
        cruft_table.add_column("Path")
        cruft_table.add_column("Explanation")
        for finding in report.cruft_findings:
            cruft_table.add_row(
                finding.label,
                _format_bytes(finding.total_size_bytes),
                finding.path,
                finding.explanation,
            )
        console.print(cruft_table)
        console.print(
            "[dim]Report-only -- searchat never deletes or modifies these.[/dim]"
        )

    if report.duplicate_suggestions:
        dedup_table = Table(
            show_header=True,
            header_style="bold",
            title="\nDuplicate Suggestions (cross-connector)",
        )
        dedup_table.add_column("Connector A")
        dedup_table.add_column("Conversation A")
        dedup_table.add_column("Connector B")
        dedup_table.add_column("Conversation B")
        dedup_table.add_column("Similarity", justify="right")
        for suggestion in report.duplicate_suggestions:
            dedup_table.add_row(
                suggestion.connector_a,
                suggestion.title_a,
                suggestion.connector_b,
                suggestion.title_b,
                f"{suggestion.similarity:.2f}",
            )
        console.print(dedup_table)
        console.print(
            "[dim]Report-only -- review and merge/ignore manually; searchat never merges or deletes these.[/dim]"
        )

    return 0
