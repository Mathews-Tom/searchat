"""CLI commands for L2 expertise store interaction."""
from __future__ import annotations

import argparse
import sys


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="searchat expertise",
        description="Expertise store commands.",
    )
    sub = parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")
    sub.required = True

    # list
    list_p = sub.add_parser("list", help="List expertise records.")
    list_p.add_argument("--domain", default=None, help="Filter by domain.")
    list_p.add_argument("--type", dest="type_", default=None, help="Filter by type.")
    list_p.add_argument("--project", default=None, help="Filter by project.")
    list_p.add_argument("--tags", default=None, help="Comma-separated tag filter.")
    list_p.add_argument("--limit", type=int, default=50, help="Max records to show.")
    list_p.add_argument(
        "--active-only",
        action="store_true",
        default=True,
        help="Only show active records (default: True).",
    )

    # record
    record_p = sub.add_parser("record", help="Record new expertise.")
    record_p.add_argument("--type", dest="type_", required=True, help="Record type.")
    record_p.add_argument("--domain", required=True, help="Domain name.")
    record_p.add_argument("--content", required=True, help="Expertise content.")
    record_p.add_argument("--project", default=None, help="Project name.")
    record_p.add_argument("--severity", default=None, help="Severity level.")
    record_p.add_argument("--tags", default=None, help="Comma-separated tags.")
    record_p.add_argument("--name", default=None, help="Record name.")
    record_p.add_argument("--rationale", default=None, help="Decision rationale.")
    record_p.add_argument("--resolution", default=None, help="Failure resolution.")

    # prime
    prime_p = sub.add_parser("prime", help="Print priming output.")
    prime_p.add_argument("--domain", default=None, help="Filter by domain.")
    prime_p.add_argument("--project", default=None, help="Filter by project.")
    prime_p.add_argument(
        "--max-tokens", type=int, default=4000, help="Token budget."
    )
    prime_p.add_argument(
        "--format",
        dest="format_",
        choices=["json", "markdown", "prompt"],
        default="markdown",
        help="Output format.",
    )

    # status
    status_p = sub.add_parser("status", help="Domain health summary.")
    status_p.add_argument("--domain", default=None, help="Filter to specific domain.")
    status_p.add_argument("--project", default=None, help="Filter by project.")

    # search
    search_p = sub.add_parser("search", help="Search expertise records.")
    search_p.add_argument("query", help="Search query string.")
    search_p.add_argument("--domain", default=None, help="Filter by domain.")
    search_p.add_argument("--type", dest="type_", default=None, help="Filter by type.")
    search_p.add_argument("--limit", type=int, default=10, help="Max results.")

    return parser


def _print_error(msg: str) -> None:
    print(f"Error: {msg}", file=sys.stderr)


def _cmd_list(args: argparse.Namespace) -> int:
    from rich.console import Console
    from rich.table import Table

    from searchat.config import Config, PathResolver
    from searchat.expertise.models import ExpertiseQuery, ExpertiseType
    from searchat.expertise.store import ExpertiseStore

    config = Config.load()
    if not config.expertise.enabled:
        _print_error("Expertise store is disabled in config.")
        return 1

    search_dir = PathResolver.get_shared_search_dir(config)
    store = ExpertiseStore(search_dir)

    tags: list[str] | None = None
    if args.tags:
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    type_filter = None
    if args.type_:
        try:
            type_filter = ExpertiseType(args.type_)
        except ValueError:
            _print_error(f"Invalid type: {args.type_}. Valid: {[t.value for t in ExpertiseType]}")
            return 1

    q = ExpertiseQuery(
        domain=args.domain,
        type=type_filter,
        project=args.project,
        tags=tags,
        active_only=args.active_only,
        limit=args.limit,
    )
    records = store.query(q)

    console = Console()
    if not records:
        console.print("[yellow]No records found.[/yellow]")
        return 0

    table = Table(title=f"Expertise Records ({len(records)})", show_lines=False)
    table.add_column("ID", style="dim", no_wrap=True, max_width=18)
    table.add_column("Type", style="cyan")
    table.add_column("Domain", style="magenta")
    table.add_column("Confidence", justify="right")
    table.add_column("Active", justify="center")
    table.add_column("Content", no_wrap=False, max_width=60)

    for rec in records:
        active_str = "[green]Y[/green]" if rec.is_active else "[red]N[/red]"
        id_display = (rec.id[:16] + "…") if len(rec.id) > 16 else rec.id
        content_preview = (rec.content[:80] + "…") if len(rec.content) > 80 else rec.content
        table.add_row(
            id_display,
            rec.type.value,
            rec.domain,
            f"{rec.confidence:.2f}",
            active_str,
            content_preview,
        )

    console.print(table)
    return 0


def _cmd_record(args: argparse.Namespace) -> int:
    from rich.console import Console

    from searchat.config import Config, PathResolver
    from searchat.expertise.models import ExpertiseRecord, ExpertiseSeverity, ExpertiseType
    from searchat.expertise.store import ExpertiseStore

    config = Config.load()
    if not config.expertise.enabled:
        _print_error("Expertise store is disabled in config.")
        return 1

    try:
        record_type = ExpertiseType(args.type_)
    except ValueError:
        _print_error(f"Invalid type: {args.type_}. Valid: {[t.value for t in ExpertiseType]}")
        return 1

    severity = None
    if args.severity:
        try:
            severity = ExpertiseSeverity(args.severity)
        except ValueError:
            _print_error(
                f"Invalid severity: {args.severity}. Valid: {[s.value for s in ExpertiseSeverity]}"
            )
            return 1

    tags: list[str] = []
    if args.tags:
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    record = ExpertiseRecord(
        type=record_type,
        domain=args.domain,
        content=args.content,
        project=args.project,
        severity=severity,
        tags=tags,
        name=args.name,
        rationale=args.rationale,
        resolution=args.resolution,
    )

    search_dir = PathResolver.get_shared_search_dir(config)
    store = ExpertiseStore(search_dir)
    record_id = store.insert(record)

    console = Console()
    console.print(f"[green]Recorded expertise:[/green] {record_id}")
    console.print(f"  type:    {record_type.value}")
    console.print(f"  domain:  {args.domain}")
    console.print(f"  content: {args.content[:80]}")
    return 0


def _cmd_prime(args: argparse.Namespace) -> int:
    from searchat.config import Config, PathResolver
    from searchat.expertise.models import ExpertiseQuery
    from searchat.expertise.primer import ExpertisePrioritizer, PrimeFormatter
    from searchat.expertise.store import ExpertiseStore

    config = Config.load()
    if not config.expertise.enabled:
        _print_error("Expertise store is disabled in config.")
        return 1

    search_dir = PathResolver.get_shared_search_dir(config)
    store = ExpertiseStore(search_dir)

    q = ExpertiseQuery(
        domain=args.domain,
        project=args.project,
        active_only=True,
        limit=100_000,
    )
    records = store.query(q)

    prioritizer = ExpertisePrioritizer()
    result = prioritizer.prioritize(records, max_tokens=args.max_tokens)

    formatter = PrimeFormatter()
    format_ = args.format_

    if format_ == "json":
        import json
        payload = formatter.format_json(
            result,
            contradiction_ids=getattr(prioritizer, "_contradiction_ids", None),
            qualifying_notes=getattr(prioritizer, "_qualifying_notes", None),
        )
        print(json.dumps(payload, indent=2))
    elif format_ == "prompt":
        output = formatter.format_prompt(
            result,
            project=args.project,
            contradiction_ids=getattr(prioritizer, "_contradiction_ids", None),
            qualifying_notes=getattr(prioritizer, "_qualifying_notes", None),
        )
        print(output)
    else:
        output = formatter.format_markdown(
            result,
            project=args.project,
            contradiction_ids=getattr(prioritizer, "_contradiction_ids", None),
            qualifying_notes=getattr(prioritizer, "_qualifying_notes", None),
        )
        print(output)

    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    from rich.console import Console
    from rich.table import Table

    from searchat.config import Config, PathResolver
    from searchat.expertise.store import ExpertiseStore

    config = Config.load()
    if not config.expertise.enabled:
        _print_error("Expertise store is disabled in config.")
        return 1

    search_dir = PathResolver.get_shared_search_dir(config)
    store = ExpertiseStore(search_dir)

    console = Console()

    if args.domain:
        domains = [args.domain]
    else:
        domain_rows = store.list_domains()
        domains = [d["name"] for d in domain_rows]

    if not domains:
        console.print("[yellow]No domains found.[/yellow]")
        return 0

    table = Table(title="Expertise Domain Health", show_lines=False)
    table.add_column("Domain", style="cyan")
    table.add_column("Total", justify="right")
    table.add_column("Active", justify="right")
    table.add_column("Avg Conf", justify="right")
    table.add_column("By Type", no_wrap=False, max_width=40)

    for domain in domains:
        stats = store.get_domain_stats(domain)
        by_type_str = ", ".join(
            f"{k}:{v}" for k, v in stats.get("by_type", {}).items()
        )
        table.add_row(
            domain,
            str(stats.get("total_records", 0)),
            str(stats.get("active_records", 0)),
            f"{stats.get('avg_confidence', 0.0):.2f}",
            by_type_str or "-",
        )

    console.print(table)
    return 0


def _cmd_search(args: argparse.Namespace) -> int:
    from rich.console import Console
    from rich.table import Table

    from searchat.config import Config, PathResolver
    from searchat.expertise.models import ExpertiseQuery, ExpertiseType
    from searchat.expertise.store import ExpertiseStore

    config = Config.load()
    if not config.expertise.enabled:
        _print_error("Expertise store is disabled in config.")
        return 1

    type_filter = None
    if args.type_:
        try:
            type_filter = ExpertiseType(args.type_)
        except ValueError:
            _print_error(f"Invalid type: {args.type_}. Valid: {[t.value for t in ExpertiseType]}")
            return 1

    search_dir = PathResolver.get_shared_search_dir(config)
    store = ExpertiseStore(search_dir)

    q = ExpertiseQuery(
        q=args.query,
        domain=args.domain,
        type=type_filter,
        active_only=True,
        limit=args.limit,
    )
    records = store.query(q)

    console = Console()
    if not records:
        console.print("[yellow]No matching records.[/yellow]")
        return 0

    table = Table(title=f"Search Results: '{args.query}' ({len(records)} found)", show_lines=False)
    table.add_column("ID", style="dim", no_wrap=True, max_width=18)
    table.add_column("Type", style="cyan")
    table.add_column("Domain", style="magenta")
    table.add_column("Confidence", justify="right")
    table.add_column("Content", no_wrap=False, max_width=60)

    for rec in records:
        id_display = (rec.id[:16] + "…") if len(rec.id) > 16 else rec.id
        content_preview = (rec.content[:80] + "…") if len(rec.content) > 80 else rec.content
        table.add_row(
            id_display,
            rec.type.value,
            rec.domain,
            f"{rec.confidence:.2f}",
            content_preview,
        )

    console.print(table)
    return 0


def run_expertise(argv: list[str]) -> int:
    """Entry point for `searchat expertise` subcommands."""
    parser = _build_parser()

    if not argv:
        parser.print_help()
        return 0

    args = parser.parse_args(argv)

    if args.subcommand == "list":
        return _cmd_list(args)
    elif args.subcommand == "record":
        return _cmd_record(args)
    elif args.subcommand == "prime":
        return _cmd_prime(args)
    elif args.subcommand == "status":
        return _cmd_status(args)
    elif args.subcommand == "search":
        return _cmd_search(args)

    parser.print_help()
    return 1
