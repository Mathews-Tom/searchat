"""CLI command: searchat ci-check — expertise health check for CI pipelines."""
from __future__ import annotations

import argparse
import sys


def run_ci_check(argv: list[str]) -> int:
    """Entry point for `searchat ci-check`.

    Exit code 0 if healthy, 1 if issues found.
    Designed for CI pipelines.
    """
    parser = argparse.ArgumentParser(
        prog="searchat ci-check",
        description="Expertise health check for CI pipelines. Exits 1 if issues found.",
    )
    parser.add_argument(
        "--fail-on-contradictions",
        action="store_true",
        default=False,
        help="Fail if any unresolved contradictions exist.",
    )
    parser.add_argument(
        "--fail-on-staleness-threshold",
        type=float,
        default=None,
        metavar="FLOAT",
        help="Fail if any records exceed this staleness threshold (0.0-1.0).",
    )
    args = parser.parse_args(argv)

    from searchat.config import Config, PathResolver
    from searchat.expertise.staleness import StalenessManager
    from searchat.expertise.store import ExpertiseStore

    config = Config.load()
    if not config.expertise.enabled:
        print("SKIP: Expertise store is disabled.", flush=True)
        return 0

    search_dir = PathResolver.get_shared_search_dir(config)
    store = ExpertiseStore(search_dir)

    issues: list[str] = []

    # Staleness check
    if args.fail_on_staleness_threshold is not None:
        threshold = args.fail_on_staleness_threshold
        if not (0.0 <= threshold <= 1.0):
            print(f"Error: --fail-on-staleness-threshold must be 0.0-1.0, got {threshold}", file=sys.stderr)
            return 1
        manager = StalenessManager(store, config)
        stale_pairs = manager.get_stale_records(threshold=threshold)
        if stale_pairs:
            issues.append(
                f"FAIL: {len(stale_pairs)} records exceed staleness threshold {threshold:.2f}"
            )
        else:
            print(f"OK: No records exceed staleness threshold {threshold:.2f}", flush=True)

    # Contradictions check
    if args.fail_on_contradictions:
        if not config.knowledge_graph.enabled:
            print("SKIP: Knowledge graph is disabled — skipping contradiction check.", flush=True)
        else:
            from searchat.knowledge_graph import KnowledgeGraphStore

            kg_store = KnowledgeGraphStore(search_dir)
            unresolved = kg_store.get_contradictions(unresolved_only=True)
            kg_store.close()
            if unresolved:
                issues.append(
                    f"FAIL: {len(unresolved)} unresolved contradiction(s) found"
                )
            else:
                print("OK: No unresolved contradictions.", flush=True)

    if not args.fail_on_contradictions and args.fail_on_staleness_threshold is None:
        # No checks requested — just verify expertise is accessible
        domains = store.list_domains()
        print(
            f"OK: Expertise store accessible. {len(domains)} domain(s) found.",
            flush=True,
        )
        return 0

    if issues:
        for issue in issues:
            print(issue, flush=True)
        return 1

    return 0
