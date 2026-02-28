"""CLI command: searchat onboard — generate a CLAUDE.md / agent config from expertise."""
from __future__ import annotations

import argparse

from rich.console import Console


def run_onboard(argv: list[str]) -> int:
    """Entry point for `searchat onboard`."""
    parser = argparse.ArgumentParser(
        prog="searchat onboard",
        description="Generate agent configuration from expertise store.",
    )
    parser.add_argument("--project", default=None, help="Scope to a specific project")
    parser.add_argument("--domain", default=None, help="Scope to a specific domain")
    parser.add_argument("--max-tokens", type=int, default=None, help="Max tokens for output")
    parser.add_argument(
        "--format",
        choices=["markdown", "json", "prompt"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument("--output", "-o", default=None, help="Write output to file instead of stdout")
    args = parser.parse_args(argv)

    console = Console()

    from searchat.config import Config, PathResolver
    from searchat.expertise.models import ExpertiseQuery
    from searchat.expertise.primer import ExpertisePrioritizer, PrimeFormatter
    from searchat.expertise.store import ExpertiseStore

    config = Config.load()
    if not config.expertise.enabled:
        console.print("[red]Expertise store is disabled in config.[/red]")
        return 1

    search_dir = PathResolver.get_shared_search_dir(config)
    store = ExpertiseStore(search_dir)

    max_tokens = args.max_tokens or config.expertise.default_prime_tokens

    query = ExpertiseQuery(
        domain=args.domain,
        project=args.project,
        active_only=True,
        limit=10000,
    )
    records = store.query(query)

    if not records:
        console.print("[yellow]No expertise records found matching filters.[/yellow]")
        return 0

    prioritizer = ExpertisePrioritizer()
    result = prioritizer.prioritize(records, max_tokens=max_tokens)

    formatter = PrimeFormatter()
    if args.format == "markdown":
        output = formatter.format_markdown(result, project=args.project)
    elif args.format == "json":
        import json
        output = json.dumps(formatter.format_json(result), indent=2)
    else:
        output = formatter.format_prompt(result, project=args.project)

    if args.output:
        from pathlib import Path
        Path(args.output).write_text(output, encoding="utf-8")
        console.print(f"[green]Written to {args.output}[/green]")
    else:
        console.print(output)

    console.print(
        f"\n[dim]{result.records_included}/{result.records_total} records, "
        f"~{result.token_count} tokens, "
        f"{len(result.domains_covered)} domains[/dim]"
    )
    return 0
