"""CLI command: searchat contradictions — list knowledge graph contradictions."""
from __future__ import annotations

import argparse
import sys


def _print_error(msg: str) -> None:
    print(f"Error: {msg}", file=sys.stderr)


def run_contradictions(argv: list[str]) -> int:
    """Entry point for `searchat contradictions`."""
    parser = argparse.ArgumentParser(
        prog="searchat contradictions",
        description="List knowledge graph contradictions.",
    )
    parser.add_argument("--domain", default=None, help="Filter by domain.")
    parser.add_argument(
        "--unresolved-only",
        action="store_true",
        default=False,
        help="Only show unresolved contradictions.",
    )
    parser.add_argument("--limit", type=int, default=50, help="Max contradictions to show.")
    args = parser.parse_args(argv)

    from rich.console import Console
    from rich.table import Table

    from searchat.config import Config, PathResolver
    from searchat.expertise.store import ExpertiseStore
    from searchat.knowledge_graph import KnowledgeGraphStore

    config = Config.load()
    if not config.knowledge_graph.enabled:
        _print_error("Knowledge graph is disabled. Set knowledge_graph.enabled = true in config.")
        return 1

    search_dir = PathResolver.get_shared_search_dir(config)
    kg_store = KnowledgeGraphStore(search_dir)
    expertise_store = ExpertiseStore(search_dir)

    edges = kg_store.get_contradictions(unresolved_only=args.unresolved_only)

    if args.domain:
        filtered = []
        for edge in edges:
            rec_a = expertise_store.get(edge.source_id)
            rec_b = expertise_store.get(edge.target_id)
            if (rec_a and rec_a.domain == args.domain) or (
                rec_b and rec_b.domain == args.domain
            ):
                filtered.append(edge)
        edges = filtered

    edges = edges[: args.limit]

    console = Console()

    if not edges:
        status = "unresolved " if args.unresolved_only else ""
        domain_msg = f" in domain '{args.domain}'" if args.domain else ""
        console.print(f"[green]No {status}contradictions found{domain_msg}.[/green]")
        kg_store.close()
        return 0

    table = Table(
        title=f"Contradictions ({'unresolved only' if args.unresolved_only else 'all'}) — {len(edges)}",
        show_lines=True,
    )
    table.add_column("Edge ID", style="dim", no_wrap=True, max_width=20)
    table.add_column("Status", style="cyan", justify="center")
    table.add_column("Record A", no_wrap=False, max_width=40)
    table.add_column("Record B", no_wrap=False, max_width=40)

    for edge in edges:
        status_str = "[red]OPEN[/red]" if edge.resolution_id is None else "[green]RESOLVED[/green]"
        rec_a = expertise_store.get(edge.source_id)
        rec_b = expertise_store.get(edge.target_id)
        content_a = (
            (rec_a.content[:60] + "…") if rec_a and len(rec_a.content) > 60
            else (rec_a.content if rec_a else "<deleted>")
        )
        content_b = (
            (rec_b.content[:60] + "…") if rec_b and len(rec_b.content) > 60
            else (rec_b.content if rec_b else "<deleted>")
        )
        edge_id_display = (edge.id[:18] + "…") if len(edge.id) > 18 else edge.id
        table.add_row(edge_id_display, status_str, content_a, content_b)

    console.print(table)
    kg_store.close()
    return 0
