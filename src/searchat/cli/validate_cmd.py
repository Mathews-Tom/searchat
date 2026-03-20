"""CLI command: searchat validate — validate expertise store health."""
from __future__ import annotations

import argparse
import importlib.util
from collections import Counter
from dataclasses import dataclass
import os
import subprocess
import sys
import tempfile

from rich.console import Console
from rich.table import Table
from rich.panel import Panel


def run_validate(argv: list[str]) -> int:
    """Entry point for `searchat validate`."""
    if argv and argv[0] == "storage":
        return _run_validate_storage(argv[1:])
    if argv and argv[0] == "release":
        return _run_validate_release(argv[1:])

    parser = argparse.ArgumentParser(
        prog="searchat validate",
        description=(
            "Validate expertise store health: schema, orphans, domains, distributions. "
            "Use `searchat validate storage` for storage compatibility checks."
        ),
    )
    parser.add_argument("--domain", default=None, help="Scope to a specific domain")
    parser.add_argument("--project", default=None, help="Scope to a specific project")
    args = parser.parse_args(argv)

    console = Console()

    from searchat.config import Config, PathResolver
    from searchat.expertise.models import ExpertiseQuery
    from searchat.expertise.store import ExpertiseStore
    from searchat.expertise.staleness import compute_staleness
    from searchat.services.storage_service import build_storage_service

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
    orphans: list[str] = []
    try:
        duckdb_store = build_storage_service(search_dir, config=config)
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


def _run_validate_storage(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="searchat validate storage",
        description="Validate storage metadata and backup compatibility.",
    )
    parser.add_argument(
        "--repair",
        action="store_true",
        help="Apply safe metadata normalization for repairable storage issues.",
    )
    args = parser.parse_args(argv)

    console = Console()

    from searchat.config import Config, PathResolver
    from searchat.services.storage_health import inspect_storage_health, repair_storage_metadata

    config = Config.load()
    search_dir = PathResolver.get_shared_search_dir(config)

    report = (
        repair_storage_metadata(search_dir, embedding_model=config.embedding.model)
        if args.repair
        else inspect_storage_health(search_dir, embedding_model=config.embedding.model)
    )

    title = "Storage Validation Report"
    if args.repair:
        title += f"\n{report.repairs_applied} repair(s) applied"
    console.print(Panel(f"[bold]{title}[/bold]\n{search_dir}", expand=False))

    if not report.issues:
        console.print("[green]No storage compatibility issues detected.[/green]")
        return 0

    table = Table(show_header=True, header_style="bold")
    table.add_column("Severity")
    table.add_column("Scope")
    table.add_column("Path")
    table.add_column("Repairable")
    table.add_column("Message")

    for issue in report.issues:
        color = "red" if issue.severity == "error" else "yellow"
        table.add_row(
            f"[{color}]{issue.severity}[/{color}]",
            issue.scope,
            str(issue.path.relative_to(search_dir)) if issue.path.is_relative_to(search_dir) else str(issue.path),
            "yes" if issue.repairable else "no",
            issue.message,
        )

    console.print(table)
    return 1 if any(issue.severity == "error" for issue in report.issues) else 0


@dataclass(frozen=True)
class ReleaseValidationGroup:
    name: str
    description: str
    targets: tuple[str, ...]


RELEASE_VALIDATION_GROUPS: tuple[ReleaseValidationGroup, ...] = (
    ReleaseValidationGroup(
        name="Contracts",
        description="Public API, MCP, and UI boundary contracts.",
        targets=(
            "tests/ui",
            "tests/api/test_fragment_routes.py",
            "tests/acceptance/test_api_contract.py",
            "tests/acceptance/test_mcp_contract.py",
        ),
    ),
    ReleaseValidationGroup(
        name="Compatibility",
        description="Storage, config, and operational compatibility gates.",
        targets=(
            "tests/acceptance/test_storage_compatibility.py",
            "tests/acceptance/test_config_compatibility.py",
            "tests/acceptance/test_ops_readiness.py",
            "tests/acceptance/test_search_quality.py",
        ),
    ),
    ReleaseValidationGroup(
        name="Performance Smoke",
        description="Fast performance gates that should hold before release.",
        targets=(
            "tests/unit/perf/test_performance_gates.py",
        ),
    ),
    ReleaseValidationGroup(
        name="Packaging",
        description="Build sdist/wheel artifacts and validate package metadata.",
        targets=(),
    ),
)


def _run_validate_release(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="searchat validate release",
        description="Run the curated pre-release validation matrix.",
    )
    parser.add_argument(
        "--group",
        action="append",
        choices=[group.name.lower() for group in RELEASE_VALIDATION_GROUPS],
        dest="groups",
        help="Run only a specific release validation group. May be passed multiple times.",
    )
    args = parser.parse_args(argv)

    console = Console()
    requested = set(args.groups or [])
    groups = tuple(
        group for group in RELEASE_VALIDATION_GROUPS
        if not requested or group.name.lower() in requested
    )

    if not groups:
        console.print("[red]No release validation groups selected.[/red]")
        return 1

    requested = set(args.groups or [group.name.lower() for group in RELEASE_VALIDATION_GROUPS])
    if requested - {"packaging"} and importlib.util.find_spec("pytest") is None:
        console.print("[red]pytest is not installed. Install dev dependencies before running release validation.[/red]")
        return 1

    console.print(
        Panel(
            "[bold]Release Validation Report[/bold]\n"
            "Runs the curated release gate matrix used for local pre-release checks.",
            expand=False,
        )
    )

    table = Table(show_header=True, header_style="bold")
    table.add_column("Group")
    table.add_column("Status")
    table.add_column("Targets")

    any_failures = False
    for group in groups:
        console.print(f"\n[bold]{group.name}[/bold]")
        console.print(group.description)
        if group.name == "Packaging":
            completed = _run_release_packaging_group(console)
        else:
            command = [
                sys.executable,
                "-m",
                "pytest",
                "-o",
                "addopts=",
                *group.targets,
                "-q",
            ]
            console.print(f"[dim]{' '.join(command)}[/dim]")
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )

        success = completed.returncode == 0
        any_failures = any_failures or not success
        status_text = "[green]PASS[/green]" if success else "[red]FAIL[/red]"

        output = (completed.stdout or "").strip()
        if output:
            console.print(output)
        error_output = (completed.stderr or "").strip()
        if error_output:
            console.print(f"[red]{error_output}[/red]")

        table.add_row(
            group.name,
            status_text,
            "\n".join(group.targets),
        )

    console.print("\n")
    console.print(table)
    return 1 if any_failures else 0


def _run_release_packaging_group(console: Console) -> subprocess.CompletedProcess[str]:
    if importlib.util.find_spec("build") is None:
        return subprocess.CompletedProcess(
            args=[sys.executable, "-m", "build"],
            returncode=1,
            stdout="",
            stderr="Python package `build` is not installed. Install dev dependencies before running packaging validation.",
        )

    with tempfile.TemporaryDirectory(prefix="searchat-release-build-") as tmp_dir:
        build_command = [
            sys.executable,
            "-m",
            "build",
            "--sdist",
            "--wheel",
            "--outdir",
            tmp_dir,
        ]
        console.print(f"[dim]{' '.join(build_command)}[/dim]")

        build_result = subprocess.run(
            build_command,
            capture_output=True,
            text=True,
            check=False,
        )
        if build_result.returncode != 0:
            return build_result

        if importlib.util.find_spec("twine") is None:
            return subprocess.CompletedProcess(
                args=build_command,
                returncode=0,
                stdout=(build_result.stdout or "").strip() + "\nTwine not installed; skipped metadata verification.",
                stderr=build_result.stderr or "",
            )

        artifacts = sorted(
            os.path.join(tmp_dir, name)
            for name in os.listdir(tmp_dir)
            if name.endswith((".whl", ".tar.gz"))
        )
        twine_command = [sys.executable, "-m", "twine", "check", *artifacts]
        console.print(f"[dim]{' '.join(twine_command)}[/dim]")

        twine_result = subprocess.run(
            twine_command,
            capture_output=True,
            text=True,
            check=False,
        )
        if twine_result.returncode != 0:
            return twine_result

        stdout_parts = [part.strip() for part in (build_result.stdout, twine_result.stdout) if part and part.strip()]
        stderr_parts = [part.strip() for part in (build_result.stderr, twine_result.stderr) if part and part.strip()]
        return subprocess.CompletedProcess(
            args=build_command,
            returncode=0,
            stdout="\n".join(stdout_parts),
            stderr="\n".join(stderr_parts),
        )


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
