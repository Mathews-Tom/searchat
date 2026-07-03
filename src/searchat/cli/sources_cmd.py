"""CLI command: searchat sources archive / searchat sources prune -- M8
verified archive-then-prune of source conversation files.

Both subcommands are dry-run by default: they report which files WOULD be
archived/pruned without touching disk. A real mutation requires the
explicit `--dry-run=false` flag -- there is no other way to opt out of
dry-run mode from this CLI, independent of any `lifecycle.dry_run` config
value. Neither subcommand ever acts on a file that hasn't passed BOTH
`verify_ingested` and `verify_roundtrip`; that gate is enforced inside
`services.source_lifecycle.run_lifecycle_action`, not here.
"""
from __future__ import annotations

import argparse
import json
import sys


def _parse_dry_run(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in ("true", "1", "yes"):
        return True
    if normalized in ("false", "0", "no"):
        return False
    raise argparse.ArgumentTypeError(f"--dry-run must be 'true' or 'false', got {value!r}")


def _build_parser(action: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=f"searchat sources {action}",
        description=(
            f"{action.capitalize()} source conversation files that are both age-gated "
            "(lifecycle.age_threshold_days) and explicitly opted in per connector "
            "(lifecycle.enabled_agents), after verifying each one is fully ingested "
            "(checksum + message-count parity) and losslessly reversible (export "
            "round trip). Neither verification is skippable in code; a file failing "
            f"either is never {action}d."
        ),
    )
    parser.add_argument(
        "--dry-run",
        type=_parse_dry_run,
        default=True,
        metavar="{true,false}",
        help=(
            "Defaults to true: report what WOULD happen without touching disk. "
            "Pass --dry-run=false explicitly to perform the real action -- there is "
            "no other way to enable it from this command."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of a summary.")
    return parser


def _run(argv: list[str], *, action: str) -> int:
    parser = _build_parser(action)
    args = parser.parse_args(argv)

    from searchat.config import Config, PathResolver
    from searchat.services.source_lifecycle import run_lifecycle_action

    config = Config.load()
    search_dir = PathResolver.get_shared_search_dir(config)
    db_path = config.storage.resolve_duckdb_path(search_dir)
    tombstone_dir = search_dir / "tombstones"

    try:
        decisions = run_lifecycle_action(
            db_path=db_path,
            policy=config.lifecycle,
            action=action,
            dry_run=args.dry_run,
            tombstone_dir=tombstone_dir,
            retention=config.retention,
        )
    except Exception as exc:
        print(f"Error: failed to run sources {action}: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps([d.to_dict() for d in decisions], indent=2))
        return 0

    from rich.console import Console

    console = Console()

    if args.dry_run:
        console.print(
            f"[bold yellow]Dry run[/bold yellow] -- searchat sources {action} "
            "(pass --dry-run=false to act)"
        )
    else:
        console.print(f"[bold green]searchat sources {action}[/bold green]")

    if not decisions:
        console.print("[dim]No indexed source files found.[/dim]")
        return 0

    acted = [d for d in decisions if d.action_taken]
    pending = [d for d in decisions if d.eligible and not d.action_taken]
    skipped = [d for d in decisions if not d.eligible]

    for decision in acted:
        console.print(f"  [green]{decision.action_taken}d[/green]  {decision.file_path}")
    for decision in pending:
        console.print(f"  [yellow]would {action}[/yellow]  {decision.file_path}")

    console.print(
        f"\n{len(acted)} {action}d, {len(pending)} eligible (dry run), "
        f"{len(skipped)} skipped, {len(decisions)} total."
    )
    return 0


def run_sources_archive(argv: list[str]) -> int:
    return _run(argv, action="archive")


def run_sources_prune(argv: list[str]) -> int:
    return _run(argv, action="prune")


def run_sources(argv: list[str]) -> int:
    """Dispatch `searchat sources <archive|prune> ...`."""
    if not argv or argv[0] not in ("archive", "prune"):
        print("Usage: searchat sources <archive|prune> [--dry-run=true|false] [--json]", file=sys.stderr)
        return 1
    subcommand, rest = argv[0], argv[1:]
    if subcommand == "archive":
        return run_sources_archive(rest)
    return run_sources_prune(rest)
