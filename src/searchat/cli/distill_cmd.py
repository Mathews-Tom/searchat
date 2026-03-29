"""CLI command for running palace distillation."""
from __future__ import annotations

import sys
import time


def run_distill(argv: list[str]) -> int:
    """Run palace distillation on pending conversations.

    Usage: searchat distill [--project PROJECT] [--retry-errors] [--dry-run]
    """
    project_id: str | None = None
    retry_errors = False
    dry_run = False

    args = list(argv)
    while args:
        arg = args.pop(0)
        if arg == "--project" and args:
            project_id = args.pop(0)
        elif arg == "--retry-errors":
            retry_errors = True
        elif arg == "--dry-run":
            dry_run = True
        elif arg in ("-h", "--help"):
            print("Usage: searchat distill [--project PROJECT] [--retry-errors] [--dry-run]")
            print()
            print("Distill pending conversations into the Memory Palace.")
            print()
            print("Options:")
            print("  --project PROJECT   Filter by project ID")
            print("  --retry-errors      Clear LLM error skips and retry")
            print("  --dry-run           List pending conversations without distilling")
            return 0
        else:
            print(f"Unknown argument: {arg}", file=sys.stderr)
            return 1

    from searchat.config import Config, PathResolver

    config = Config.load()
    if not config.palace.enabled:
        print("Palace is not enabled. Set [palace] enabled = true in settings.toml")
        return 1

    search_dir = PathResolver.get_shared_search_dir(config)
    data_dir = search_dir / "data"

    from searchat.palace.storage import PalaceStorage

    palace_storage = PalaceStorage(data_dir)

    if retry_errors:
        cleared = palace_storage.clear_llm_error_skips()
        print(f"Cleared {cleared} LLM error skips for retry.")

    from searchat.palace.llm import CLIDistillationLLM
    from searchat.palace.distiller import Distiller

    llm = CLIDistillationLLM(
        provider=config.distillation.provider,
        model=config.distillation.cli_model,
        prompt_template=config.distillation.prompt,
    )

    # Get a duckdb_store for reading conversations
    from searchat.services.storage_service import build_storage_service

    duckdb_store = build_storage_service(search_dir, config=config)

    distiller = Distiller(
        search_dir=search_dir,
        config=config,
        llm=llm,
        duckdb_store=duckdb_store,
        palace_storage=palace_storage,
    )

    pending = distiller.list_pending_conversations(project_id)
    print(f"Found {len(pending)} pending conversations.")

    if dry_run:
        for conv_id in pending[:20]:
            print(f"  {conv_id}")
        if len(pending) > 20:
            print(f"  ... and {len(pending) - 20} more")
        return 0

    if not pending:
        print("Nothing to distill.")
        return 0

    start = time.time()
    stats = distiller.distill_all_pending(project_id)
    elapsed = time.time() - start

    print(f"Distilled {stats.conversations_processed} conversations")
    print(f"  Objects created: {stats.objects_created}")
    print(f"  Time: {elapsed:.1f}s")

    distiller.close()
    return 0
