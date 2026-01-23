"""
Custom Indexing Example

Demonstrates programmatic control over indexing.
Use case: Manual index updates, selective indexing, monitoring index status.

WARNING: This example is read-only to protect existing data.
Modify carefully if you need to enable indexing operations.

Usage:
    python examples/custom_indexing.py
"""

from pathlib import Path
from searchat.indexer import ConversationIndexer
from searchat.config import Config
from searchat.path_resolver import PathResolver


def check_index_status():
    """Check current index statistics."""
    config = Config.load()
    indexer = ConversationIndexer(config)

    print("Index Status")
    print("=" * 70)

    # Get statistics
    stats = indexer.get_stats()

    print(f"Total conversations: {stats.get('total_conversations', 0)}")
    print(f"Total messages: {stats.get('total_messages', 0)}")
    print(f"Index size: {stats.get('index_size_mb', 0):.2f} MB")
    print(f"Last updated: {stats.get('last_updated', 'Never')}")


def list_indexed_conversations():
    """List all indexed conversations."""
    config = Config.load()
    indexer = ConversationIndexer(config)

    print("\nIndexed Conversations")
    print("=" * 70)

    # Get list of indexed files
    indexed = indexer.list_indexed_files()

    for i, file_info in enumerate(indexed[:10], 1):  # Show first 10
        print(f"{i}. {file_info['name']}")
        print(f"   Path: {file_info['path']}")
        print(f"   Messages: {file_info.get('message_count', 'Unknown')}")
        print()

    total = len(indexed)
    if total > 10:
        print(f"... and {total - 10} more")

    print(f"\nTotal: {total} conversations indexed")


def find_unindexed_conversations():
    """Find conversations that haven't been indexed yet."""
    config = Config.load()
    indexer = ConversationIndexer(config)

    print("\nUnindexed Conversations")
    print("=" * 70)

    # Get all conversation files
    claude_dirs = PathResolver.resolve_claude_dirs(config)
    all_conversations = []

    for claude_dir in claude_dirs:
        conversations_path = claude_dir / "projects"
        if conversations_path.exists():
            for conv_file in conversations_path.rglob("*.jsonl"):
                all_conversations.append(conv_file)

    # Get indexed files
    indexed = set(indexer.list_indexed_files())

    # Find unindexed
    unindexed = [conv for conv in all_conversations if str(conv) not in indexed]

    if unindexed:
        for i, conv_path in enumerate(unindexed[:10], 1):
            print(f"{i}. {conv_path.name}")
            print(f"   Path: {conv_path}")
            print()

        total = len(unindexed)
        if total > 10:
            print(f"... and {total - 10} more")

        print(f"\nTotal: {total} unindexed conversations")
    else:
        print("All conversations are indexed!")


def main():
    """Run custom indexing examples."""
    print("Custom Indexing Operations")
    print("=" * 70)
    print()

    # Example 1: Check index status
    check_index_status()
    print()

    # Example 2: List indexed conversations
    list_indexed_conversations()
    print()

    # Example 3: Find unindexed conversations
    find_unindexed_conversations()
    print()

    print("=" * 70)
    print("NOTE: Indexing operations (add/remove/rebuild) are disabled")
    print("to protect existing data. See CLAUDE.md for data safety info.")


if __name__ == "__main__":
    main()
