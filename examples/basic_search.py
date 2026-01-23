"""
Basic Search Example

Demonstrates simple search with default configuration.
Use case: Quick keyword search across all conversations.

Usage:
    python examples/basic_search.py
"""

from searchat.search_engine import SearchEngine
from searchat.config import Config


def main():
    """Run a basic search query."""
    # Load default configuration
    config = Config.load()

    # Initialize search engine
    engine = SearchEngine(config)

    # Perform a simple search
    query = "refactoring"
    print(f"Searching for: '{query}'")
    print("-" * 70)

    results = engine.search(query, mode="hybrid", max_results=5)

    # Display results
    for i, result in enumerate(results, 1):
        print(f"\n{i}. {result.conversation_name}")
        print(f"   Score: {result.score:.2f}")
        print(f"   File: {result.file_path}")
        print(f"   Snippet: {result.snippet[:150]}...")

    print(f"\n\nFound {len(results)} results")


if __name__ == "__main__":
    main()
