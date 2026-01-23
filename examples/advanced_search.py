"""
Advanced Search Example

Demonstrates custom filters and multiple search modes.
Use case: Targeted search with date ranges and custom filters.

Usage:
    python examples/advanced_search.py
"""

from datetime import datetime, timedelta
from searchat.search_engine import SearchEngine
from searchat.models import SearchFilters, SearchMode
from searchat.config import Config


def search_with_filters():
    """Search with date range and custom filters."""
    config = Config.load()
    engine = SearchEngine(config)

    # Define search query
    query = "API design"

    # Create filters for recent conversations
    last_30_days = datetime.now() - timedelta(days=30)
    filters = SearchFilters(
        start_date=last_30_days,
        end_date=datetime.now(),
        min_score=0.5,  # Only high-relevance results
    )

    print(f"Searching for: '{query}'")
    print(f"Date range: {last_30_days.date()} to {datetime.now().date()}")
    print(f"Min score: {filters.min_score}")
    print("-" * 70)

    # Perform search
    results = engine.search(
        query,
        mode="hybrid",
        filters=filters,
        max_results=10
    )

    # Display results
    for i, result in enumerate(results, 1):
        print(f"\n{i}. {result.conversation_name}")
        print(f"   Score: {result.score:.3f}")
        print(f"   Date: {result.created_at.date() if result.created_at else 'Unknown'}")
        print(f"   Snippet: {result.snippet[:200]}...")

    print(f"\n\nFound {len(results)} results")


def compare_search_modes():
    """Compare results from different search modes."""
    config = Config.load()
    engine = SearchEngine(config)

    query = "error handling patterns"

    print(f"Comparing search modes for: '{query}'")
    print("=" * 70)

    modes = ["keyword", "semantic", "hybrid"]

    for mode in modes:
        print(f"\n{mode.upper()} SEARCH:")
        print("-" * 70)

        results = engine.search(query, mode=mode, max_results=3)

        for i, result in enumerate(results, 1):
            print(f"{i}. {result.conversation_name} (score: {result.score:.3f})")

        print(f"Total: {len(results)} results")


def main():
    """Run advanced search examples."""
    print("EXAMPLE 1: Search with filters")
    print("=" * 70)
    search_with_filters()

    print("\n\n")

    print("EXAMPLE 2: Compare search modes")
    print("=" * 70)
    compare_search_modes()


if __name__ == "__main__":
    main()
