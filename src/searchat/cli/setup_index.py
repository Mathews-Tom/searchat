from __future__ import annotations

import sys

from searchat.config import Config, PathResolver
from searchat.core.connectors import get_connectors
from searchat.core.indexer import ConversationIndexer
from searchat.core.logging_config import setup_logging
from searchat.core.progress import create_progress


def main() -> None:
    """Build the initial index for a dataset.

    This is intended for first-time setup after installing Searchat.

    Usage:
        searchat-setup-index [--force]

    Behavior:
        - If no index exists: builds a full index.
        - If an index exists and --force is not set:
            - In a TTY: prompts for append-only vs full rebuild.
            - Non-interactive: defaults to append-only.
    """
    print("=" * 70)
    print("Searchat - Initial Index Setup")
    print("=" * 70)
    print()

    force = "--force" in sys.argv

    try:
        print("Loading configuration...")
        config = Config.load()

        setup_logging(config.logging)

        search_dir = PathResolver.get_shared_search_dir(config)
        print(f"Search directory: {search_dir}")
        print(f"Data directory: {search_dir}/data")
        print()

        print("Initializing indexer...")
        indexer = ConversationIndexer(search_dir, config)

        has_index = indexer._has_existing_index()
        use_append_only = False

        if has_index and not force:
            if sys.stdin.isatty():
                print("Existing index detected.")
                print()
                print(f"Index location: {search_dir}/data")
                print()
                print("Options:")
                print("  1. Keep existing index and add only new conversations (SAFE)")
                print("  2. Rebuild entire index from scratch (WARNING: replaces all data)")
                print("  3. Exit without changes")
                print()

                while True:
                    choice = input("Enter your choice (1/2/3): ").strip()
                    if choice == "1":
                        use_append_only = True
                        break
                    if choice == "2":
                        confirm = input(
                            "Are you sure? This will replace all indexed data. Type 'yes' to confirm: "
                        ).strip()
                        if confirm.lower() == "yes":
                            force = True
                            use_append_only = False
                            break
                        print("Cancelled.")
                        return
                    if choice == "3":
                        print("Exiting without changes.")
                        return
                    print("Invalid choice. Please enter 1, 2, or 3.")
            else:
                # Non-interactive safety default.
                use_append_only = True

        progress = create_progress()

        if use_append_only:
            print("Finding new conversations to index...")
            print()

            all_files: list[str] = []
            for connector in get_connectors():
                for path in connector.discover_files(config):
                    all_files.append(str(path))

            indexed_paths = indexer.get_indexed_file_paths()
            new_files = [f for f in all_files if f not in indexed_paths]

            print(f"Total conversation files: {len(all_files)}")
            print(f"Already indexed: {len(indexed_paths)}")
            print(f"New files to index: {len(new_files)}")
            print()

            if not new_files:
                print("No new conversations to index. Your index is up to date.")
                print()
                print("Start the web server with:")
                print("  searchat-web")
                return

            stats = indexer.index_append_only(new_files, progress)

            print()
            print("=" * 70)
            print("Index Update Complete")
            print("=" * 70)
            print(f"New conversations indexed: {stats.new_conversations}")
            print(f"Index time: {stats.update_time_seconds:.2f} seconds")
            print()
        else:
            print("Building index from all conversation files...")
            print("This may take a few minutes depending on the number of conversations.")
            print()

            stats = indexer.index_all(force=force, progress=progress)

            print()
            print("=" * 70)
            print("Index Build Complete")
            print("=" * 70)
            print(f"Total conversations: {stats.total_conversations}")
            print(f"Total messages: {stats.total_messages}")
            print(f"Index time: {stats.index_time_seconds:.2f} seconds")
            print(f"Parquet size: {stats.parquet_size_mb:.2f} MB")
            print(f"FAISS index size: {stats.faiss_size_mb:.2f} MB")
            print()

        print("Start the web server with:")
        print("  searchat-web")

    except RuntimeError as exc:
        print()
        print(f"Error: {exc}")
        raise SystemExit(1) from exc
    except FileNotFoundError as exc:
        print()
        print(f"Error: {exc}")
        raise SystemExit(1) from exc
