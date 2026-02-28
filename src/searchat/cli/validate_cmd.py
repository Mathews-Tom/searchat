"""CLI command: searchat validate — validate expertise store health."""
from __future__ import annotations

import argparse
from collections import Counter

from rich.console import Console
from rich.table import Table
from rich.panel import Panel


def run_validate(argv: list[str]) -> int:
    """Entry point for `searchat validate`."""
    parser = argparse.ArgumentParser(
        prog="searchat validate",
        description="Validate expertise store health: schema, orphans, domains, distributions.",
    )
    parser.add_argument("--domain", default=None, help="Scope to a specific domain")
    parser.add_argument("--project", default=None, help="Scope to a specific project")
    args = parser.parse_args(argv)

    console = Console()

    from searchat.config import Config, PathResolver
    from searchat.expertise.models import ExpertiseQuery
    from searchat.expertise.store import ExpertiseStore
    from searchat.expertise.staleness import compute_staleness

    config = Config.load()
    if not config.expertise.enabled:
        console.print("[red]Expertise store is disabled in config.[/red]")
        return 1

    search_dir = PathResolver.get_shared_search_dir(config)
    store = ExpertiseStore(search_dir)

    query = ExpertiseQuery(
        domain=args.domain,
        project=args.project,
        active_only=False,
        limit=10000,
    )
    all_records = store.query(query)

    if not all_records:
        console.print("[yellow]No expertise records found matching filters.[/yellow]")
        return 0

    console.print(Panel(f"[bold]Expertise Validation Report[/bold]\n{len(all_records)} records scanned", expand=False))

    # ------------------------------------------------------------------
    # 1. Schema compliance — check required fields per type
    # ------------------------------------------------------------------
    schema_issues: list[str] = []
    required_fields: dict[str, list[str]] = {
        "failure": ["resolution"],
        "decision": ["rationale"],
        "pattern": ["name"],
    }
    for record in all_records:
        reqs = required_fields.get(record.type.value, [])
        for field in reqs:
            val = getattr(record, field, None)
            if not val:
                schema_issues.append(
                    f"[{record.id[:12]}…] {record.type.value} missing '{field}'"
                )

    schema_color = "green" if not schema_issues else "yellow"
    console.print(f"\n[bold {schema_color}]1. Schema Compliance[/bold {schema_color}]")
    if schema_issues:
        for issue in schema_issues[:20]:
            console.print(f"  [yellow]WARN[/yellow] {issue}")
        if len(schema_issues) > 20:
            console.print(f"  … and {len(schema_issues) - 20} more")
    else:
        console.print("  [green]All records pass schema checks.[/green]")

    # ------------------------------------------------------------------
    # 2. Orphan detection — records referencing missing conversations
    # ------------------------------------------------------------------
    from searchat.api.duckdb_store import DuckDBStore

    orphans: list[str] = []
    try:
        duckdb_store = DuckDBStore(search_dir, memory_limit_mb=config.performance.memory_limit_mb)
        all_conv_ids: set[str] = {
            row["conversation_id"]
            for row in duckdb_store.list_conversations(limit=None) or []
        }
        for record in all_records:
            if record.source_conversation_id and record.source_conversation_id not in all_conv_ids:
                orphans.append(record.id)
    except Exception:
        all_conv_ids = set()

    orphan_color = "green" if not orphans else "yellow"
    console.print(f"\n[bold {orphan_color}]2. Orphan Detection[/bold {orphan_color}]")
    if orphans:
        console.print(f"  [yellow]{len(orphans)} records reference missing conversations.[/yellow]")
        for oid in orphans[:10]:
            console.print(f"  - {oid}")
        if len(orphans) > 10:
            console.print(f"  … and {len(orphans) - 10} more")
    else:
        console.print("  [green]No orphaned records detected.[/green]")

    # ------------------------------------------------------------------
    # 3. Domain consistency — near-duplicate domain names
    # ------------------------------------------------------------------
    domain_names = sorted({r.domain for r in all_records})
    near_dupes: list[tuple[str, str]] = []
    for i, a in enumerate(domain_names):
        for b in domain_names[i + 1:]:
            if _edit_distance(a.lower(), b.lower()) <= 2:
                near_dupes.append((a, b))

    dupe_color = "green" if not near_dupes else "yellow"
    console.print(f"\n[bold {dupe_color}]3. Domain Consistency[/bold {dupe_color}]")
    if near_dupes:
        console.print(f"  [yellow]{len(near_dupes)} near-duplicate domain name pairs:[/yellow]")
        for a, b in near_dupes:
            console.print(f"  - '{a}' vs '{b}'")
    else:
        console.print("  [green]No near-duplicate domain names found.[/green]")

    # ------------------------------------------------------------------
    # 4. Confidence distribution histogram
    # ------------------------------------------------------------------
    console.print("\n[bold]4. Confidence Distribution[/bold]")
    buckets = Counter[str]()
    bucket_labels = ["0.0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"]
    for record in all_records:
        idx = min(int(record.confidence / 0.2), 4)
        buckets[bucket_labels[idx]] += 1

    conf_table = Table(show_header=True, header_style="bold")
    conf_table.add_column("Bucket")
    conf_table.add_column("Count", justify="right")
    conf_table.add_column("Bar")
    max_count = max(buckets.values()) if buckets else 1
    for label in bucket_labels:
        count = buckets[label]
        bar = "█" * int(count / max_count * 20)
        conf_table.add_row(label, str(count), bar)
    console.print(conf_table)

    # ------------------------------------------------------------------
    # 5. Staleness distribution histogram
    # ------------------------------------------------------------------
    console.print("\n[bold]5. Staleness Distribution[/bold]")
    stale_buckets = Counter[str]()
    stale_labels = ["0.0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"]
    active_records = [r for r in all_records if r.is_active]
    for record in active_records:
        score = compute_staleness(record)
        idx = min(int(score / 0.2), 4)
        stale_buckets[stale_labels[idx]] += 1

    stale_table = Table(show_header=True, header_style="bold")
    stale_table.add_column("Staleness Bucket")
    stale_table.add_column("Count", justify="right")
    stale_table.add_column("Bar")
    max_stale = max(stale_buckets.values()) if stale_buckets else 1
    for label in stale_labels:
        count = stale_buckets[label]
        bar = "█" * int(count / max_stale * 20)
        color = "red" if label == "0.8-1.0" else "yellow" if label in ("0.6-0.8",) else "green"
        stale_table.add_row(label, str(count), f"[{color}]{bar}[/{color}]")
    console.print(stale_table)

    console.print("\n[bold green]Validation complete.[/bold green]")
    return 0


def _edit_distance(a: str, b: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[:]
        dp[0] = i
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                dp[j] = prev[j - 1]
            else:
                dp[j] = 1 + min(prev[j], dp[j - 1], prev[j - 1])
    return dp[n]
