"""CLI commands for the L3 Knowledge Graph."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="searchat graph",
        description="Knowledge graph commands.",
    )
    sub = parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")
    sub.required = True

    # stats
    sub.add_parser("stats", help="Show graph statistics.")

    # contradictions
    contra_p = sub.add_parser("contradictions", help="List contradictions.")
    contra_p.add_argument("--domain", default=None, help="Filter by domain.")
    contra_p.add_argument(
        "--unresolved-only",
        action="store_true",
        default=False,
        help="Only show unresolved contradictions.",
    )

    # resolve
    resolve_p = sub.add_parser("resolve", help="Resolve a contradiction edge.")
    resolve_p.add_argument("edge_id", help="Edge ID to resolve.")
    resolve_p.add_argument(
        "strategy",
        choices=["supersede", "scope_both", "merge", "dismiss", "keep_both"],
        help="Resolution strategy.",
    )
    resolve_p.add_argument(
        "--params",
        default=None,
        help="JSON-encoded parameters for the strategy.",
    )

    # lineage
    lineage_p = sub.add_parser("lineage", help="Show provenance chain for a record.")
    lineage_p.add_argument("record_id", help="Expertise record ID.")

    return parser


def _print_error(msg: str) -> None:
    print(f"Error: {msg}", file=sys.stderr)


def _cmd_stats(args: argparse.Namespace) -> int:
    from searchat.config import Config, PathResolver
    from searchat.knowledge_graph import KnowledgeGraphStore
    from searchat.expertise.store import ExpertiseStore
    from searchat.expertise.models import ExpertiseQuery

    config = Config.load()
    if not config.knowledge_graph.enabled:
        _print_error("Knowledge graph is disabled. Set knowledge_graph.enabled = true in config.")
        return 1

    search_dir = PathResolver.get_shared_search_dir(config)
    kg_store = KnowledgeGraphStore(search_dir)
    expertise_store = ExpertiseStore(search_dir)

    all_records = expertise_store.query(ExpertiseQuery(active_only=False, limit=100_000))
    node_count = len(all_records)
    all_contradictions = kg_store.get_contradictions(unresolved_only=False)
    unresolved = kg_store.get_contradictions(unresolved_only=True)

    from searchat.knowledge_graph.models import EdgeType

    edge_type_counts: dict[str, int] = {t.value: 0 for t in EdgeType}
    total_edges = 0
    for record in all_records:
        edges = kg_store.get_edges_for_record(record.id, as_source=True, as_target=False)
        for edge in edges:
            if edge.source_id == record.id:
                edge_type_counts[edge.edge_type.value] += 1
                total_edges += 1

    contradiction_rate = len(all_contradictions) / node_count if node_count > 0 else 0.0
    health_score = max(
        0.0,
        1.0 - (len(unresolved) / node_count if node_count > 0 else 0.0),
    )

    print("Knowledge Graph Statistics")
    print("=" * 40)
    print(f"  Nodes (records):          {node_count}")
    print(f"  Total edges:              {total_edges}")
    print(f"  Contradictions (total):   {len(all_contradictions)}")
    print(f"  Contradictions (open):    {len(unresolved)}")
    print(f"  Contradiction rate:       {contradiction_rate:.2%}")
    print(f"  Health score:             {health_score:.2f}")
    print()
    print("Edge type breakdown:")
    for etype, cnt in sorted(edge_type_counts.items()):
        if cnt:
            print(f"  {etype:<22} {cnt}")

    kg_store.close()
    return 0


def _cmd_contradictions(args: argparse.Namespace) -> int:
    from searchat.config import Config, PathResolver
    from searchat.knowledge_graph import KnowledgeGraphStore
    from searchat.expertise.store import ExpertiseStore

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

    if not edges:
        status = "unresolved " if args.unresolved_only else ""
        domain_msg = f" in domain '{args.domain}'" if args.domain else ""
        print(f"No {status}contradictions found{domain_msg}.")
        kg_store.close()
        return 0

    resolved_label = " (resolved)" if not args.unresolved_only else ""
    print(f"Contradictions{resolved_label}: {len(edges)}")
    print("-" * 60)
    for edge in edges:
        status = "OPEN" if edge.resolution_id is None else "RESOLVED"
        rec_a = expertise_store.get(edge.source_id)
        rec_b = expertise_store.get(edge.target_id)
        content_a = (rec_a.content[:60] + "...") if rec_a and len(rec_a.content) > 60 else (rec_a.content if rec_a else "<deleted>")
        content_b = (rec_b.content[:60] + "...") if rec_b and len(rec_b.content) > 60 else (rec_b.content if rec_b else "<deleted>")
        print(f"  [{status}] {edge.id}")
        print(f"    A ({edge.source_id}): {content_a}")
        print(f"    B ({edge.target_id}): {content_b}")
        print()

    kg_store.close()
    return 0


def _cmd_resolve(args: argparse.Namespace) -> int:
    from searchat.config import Config, PathResolver
    from searchat.knowledge_graph import KnowledgeGraphStore
    from searchat.knowledge_graph.models import ResolutionStrategy
    from searchat.knowledge_graph.resolver import ResolutionEngine
    from searchat.expertise.store import ExpertiseStore

    config = Config.load()
    if not config.knowledge_graph.enabled:
        _print_error("Knowledge graph is disabled. Set knowledge_graph.enabled = true in config.")
        return 1

    params: dict = {}
    if args.params:
        try:
            params = json.loads(args.params)
        except json.JSONDecodeError as exc:
            _print_error(f"Invalid --params JSON: {exc}")
            return 1

    search_dir = PathResolver.get_shared_search_dir(config)
    kg_store = KnowledgeGraphStore(search_dir)
    expertise_store = ExpertiseStore(search_dir)

    edge = kg_store.get_edge(args.edge_id)
    if edge is None:
        _print_error(f"Edge not found: {args.edge_id}")
        kg_store.close()
        return 1

    from searchat.knowledge_graph.models import EdgeType

    if edge.edge_type != EdgeType.CONTRADICTS:
        _print_error(
            f"Edge {args.edge_id} is not a CONTRADICTS edge (type={edge.edge_type.value})"
        )
        kg_store.close()
        return 1

    engine = ResolutionEngine(kg_store=kg_store, expertise_store=expertise_store)
    strategy = ResolutionStrategy(args.strategy)

    try:
        if strategy == ResolutionStrategy.SUPERSEDE:
            winner_id = params.get("winner_id")
            if not winner_id:
                _print_error("params.winner_id required for supersede strategy")
                kg_store.close()
                return 1
            result = engine.supersede(args.edge_id, winner_id)
        elif strategy == ResolutionStrategy.SCOPE_BOTH:
            scope_a = params.get("scope_a", "")
            scope_b = params.get("scope_b", "")
            if not scope_a or not scope_b:
                _print_error("params.scope_a and params.scope_b required for scope_both strategy")
                kg_store.close()
                return 1
            result = engine.scope_both(args.edge_id, scope_a, scope_b)
        elif strategy == ResolutionStrategy.MERGE:
            merged_content = params.get("merged_content", "")
            if not merged_content:
                _print_error("params.merged_content required for merge strategy")
                kg_store.close()
                return 1
            result = engine.merge(args.edge_id, merged_content)
        elif strategy == ResolutionStrategy.DISMISS:
            reason = params.get("reason", "")
            if not reason:
                _print_error("params.reason required for dismiss strategy")
                kg_store.close()
                return 1
            result = engine.dismiss(args.edge_id, reason)
        elif strategy == ResolutionStrategy.KEEP_BOTH:
            reason = params.get("reason", "")
            if not reason:
                _print_error("params.reason required for keep_both strategy")
                kg_store.close()
                return 1
            result = engine.keep_both(args.edge_id, reason)
        else:
            _print_error(f"Unsupported strategy: {strategy}")
            kg_store.close()
            return 1
    except Exception as exc:
        _print_error(f"Resolution failed: {exc}")
        kg_store.close()
        return 1

    print(f"Resolution applied: {result.resolution_id}")
    print(f"  Strategy:            {result.strategy.value}")
    print(f"  Edge:                {result.edge_id}")
    print(f"  Note:                {result.note}")
    if result.deactivated_records:
        print(f"  Deactivated records: {', '.join(result.deactivated_records)}")
    if result.created_edges:
        print(f"  Created edges:       {', '.join(result.created_edges)}")
    if result.new_record_id:
        print(f"  New record:          {result.new_record_id}")

    kg_store.close()
    return 0


def _cmd_lineage(args: argparse.Namespace) -> int:
    from searchat.config import Config, PathResolver
    from searchat.knowledge_graph import KnowledgeGraphStore
    from searchat.knowledge_graph.provenance import ProvenanceTracker
    from searchat.expertise.store import ExpertiseStore

    config = Config.load()
    if not config.knowledge_graph.enabled:
        _print_error("Knowledge graph is disabled. Set knowledge_graph.enabled = true in config.")
        return 1

    search_dir = PathResolver.get_shared_search_dir(config)
    kg_store = KnowledgeGraphStore(search_dir)
    expertise_store = ExpertiseStore(search_dir)

    record = expertise_store.get(args.record_id)
    if record is None:
        _print_error(f"Record not found: {args.record_id}")
        kg_store.close()
        return 1

    tracker = ProvenanceTracker(kg_store=kg_store)
    lineage = tracker.get_full_lineage(args.record_id)

    content_preview = (record.content[:80] + "...") if len(record.content) > 80 else record.content
    print(f"Lineage for record: {args.record_id}")
    print(f"  Content: {content_preview}")
    print(f"  Domain:  {record.domain}")
    print()

    conversations = lineage.get("conversations", [])
    derived = lineage.get("derived_records", [])

    if conversations:
        print(f"Source conversations ({len(conversations)}):")
        for cid in conversations:
            print(f"  - {cid}")
    else:
        print("No source conversations recorded.")

    if derived:
        print()
        print(f"Derived records ({len(derived)}):")
        for rid in derived:
            derived_rec = expertise_store.get(rid)
            label = derived_rec.content[:60] if derived_rec else "<deleted>"
            print(f"  - {rid}: {label}")

    kg_store.close()
    return 0


def run_graph(argv: list[str]) -> int:
    """Entry point for `searchat graph` subcommands."""
    parser = _build_parser()

    if not argv:
        parser.print_help()
        return 0

    # Let argparse handle --help and errors (raises SystemExit)
    args = parser.parse_args(argv)

    if args.subcommand == "stats":
        return _cmd_stats(args)
    elif args.subcommand == "contradictions":
        return _cmd_contradictions(args)
    elif args.subcommand == "resolve":
        return _cmd_resolve(args)
    elif args.subcommand == "lineage":
        return _cmd_lineage(args)

    parser.print_help()
    return 1
