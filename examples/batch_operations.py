"""
Batch Operations Example

Demonstrates bulk processing of conversations.
Use case: Export search results, analyze conversation patterns, generate reports.

Usage:
    python examples/batch_operations.py
"""

import json
from pathlib import Path
from datetime import datetime
from collections import Counter
from searchat.search_engine import SearchEngine
from searchat.config import Config


def export_search_results_to_json(query: str, output_file: str):
    """Export search results to JSON file."""
    config = Config.load()
    engine = SearchEngine(config)

    print(f"Searching for: '{query}'")
    results = engine.search(query, mode="hybrid", max_results=100)

    # Convert results to JSON-serializable format
    export_data = {
        "query": query,
        "timestamp": datetime.now().isoformat(),
        "total_results": len(results),
        "results": [
            {
                "conversation_name": r.conversation_name,
                "score": r.score,
                "file_path": str(r.file_path),
                "snippet": r.snippet,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in results
        ]
    }

    # Write to file
    output_path = Path(output_file)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)

    print(f"Exported {len(results)} results to {output_path}")


def analyze_conversation_topics():
    """Analyze topics across all conversations."""
    config = Config.load()
    engine = SearchEngine(config)

    # Search for different topics
    topics = [
        "python",
        "javascript",
        "refactoring",
        "testing",
        "API design",
        "database",
        "performance",
        "security",
    ]

    print("Topic Analysis Across All Conversations")
    print("=" * 70)

    topic_counts = {}

    for topic in topics:
        results = engine.search(topic, mode="hybrid", max_results=100)
        topic_counts[topic] = len(results)

    # Sort by count
    sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)

    for topic, count in sorted_topics:
        bar = "█" * (count // 2)
        print(f"{topic:20} {bar} {count}")

    print()
    print(f"Analyzed {len(topics)} topics")


def find_conversations_by_date_range(start_date: datetime, end_date: datetime):
    """Find conversations within a date range."""
    from searchat.models import SearchFilters

    config = Config.load()
    engine = SearchEngine(config)

    filters = SearchFilters(
        start_date=start_date,
        end_date=end_date,
    )

    # Use a broad query to get all conversations in range
    results = engine.search("", mode="hybrid", filters=filters, max_results=1000)

    print(f"\nConversations from {start_date.date()} to {end_date.date()}")
    print("=" * 70)

    # Group by date
    by_date = Counter()
    for result in results:
        if result.created_at:
            date = result.created_at.date()
            by_date[date] += 1

    # Display by date
    for date in sorted(by_date.keys()):
        count = by_date[date]
        print(f"{date}: {count} conversations")

    print(f"\nTotal: {len(results)} conversations")


def batch_keyword_search(keywords: list):
    """Search for multiple keywords and combine results."""
    config = Config.load()
    engine = SearchEngine(config)

    print("Batch Keyword Search")
    print("=" * 70)

    all_results = {}

    for keyword in keywords:
        results = engine.search(keyword, mode="keyword", max_results=20)
        all_results[keyword] = results
        print(f"{keyword:20} → {len(results)} results")

    # Find conversations that match multiple keywords
    print("\nConversations matching multiple keywords:")

    # Collect all unique conversations
    all_conversations = {}
    for keyword, results in all_results.items():
        for result in results:
            conv_name = result.conversation_name
            if conv_name not in all_conversations:
                all_conversations[conv_name] = set()
            all_conversations[conv_name].add(keyword)

    # Find multi-keyword matches
    multi_matches = {
        conv: keywords_matched
        for conv, keywords_matched in all_conversations.items()
        if len(keywords_matched) > 1
    }

    for conv, matched_keywords in sorted(
        multi_matches.items(),
        key=lambda x: len(x[1]),
        reverse=True
    )[:10]:
        print(f"\n{conv}")
        print(f"  Matched: {', '.join(matched_keywords)}")


def main():
    """Run batch operation examples."""
    # Example 1: Export search results
    print("EXAMPLE 1: Export to JSON")
    print("=" * 70)
    export_search_results_to_json("python testing", "search_results.json")
    print()

    # Example 2: Topic analysis
    print("\nEXAMPLE 2: Topic Analysis")
    print("=" * 70)
    analyze_conversation_topics()
    print()

    # Example 3: Batch keyword search
    print("\nEXAMPLE 3: Batch Keyword Search")
    print("=" * 70)
    keywords = ["python", "typescript", "refactor", "optimize"]
    batch_keyword_search(keywords)


if __name__ == "__main__":
    main()
