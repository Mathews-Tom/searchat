"""
API Integration Example

Demonstrates using searchat as a library in other projects.
Use case: Embed search functionality into custom tools, dashboards, or workflows.

Usage:
    python examples/api_integration.py
"""

from pathlib import Path
from typing import Any
from searchat.search_engine import SearchEngine
from searchat.models import SearchResult, SearchFilters
from searchat.config import Config


class ConversationSearchAPI:
    """
    Wrapper API for integrating searchat into other applications.

    This class provides a simplified interface for common search operations.
    """

    def __init__(self, config_path: Path = None):
        """
        Initialize the search API.

        Args:
            config_path: Optional path to custom config file
        """
        self.config = Config.load(config_path)
        self.engine = SearchEngine(self.config)

    def quick_search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        Perform a quick search and return simplified results.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of result dictionaries
        """
        results = self.engine.search(query, mode="hybrid", max_results=limit)

        return [
            {
                "title": r.conversation_name,
                "score": round(r.score, 3),
                "snippet": r.snippet,
                "path": str(r.file_path),
                "date": r.created_at.isoformat() if r.created_at else None,
            }
            for r in results
        ]

    def search_by_mode(
        self,
        query: str,
        mode: str = "hybrid",
        limit: int = 10
    ) -> list[SearchResult]:
        """
        Search with specific mode.

        Args:
            query: Search query
            mode: One of "keyword", "semantic", "hybrid"
            limit: Maximum results

        Returns:
            List of SearchResult objects
        """
        return self.engine.search(query, mode=mode, max_results=limit)

    def get_conversation_by_name(self, name: str) -> list[dict[str, Any]]:
        """
        Find conversations by name (exact or partial match).

        Args:
            name: Conversation name to search for

        Returns:
            List of matching conversations
        """
        results = self.engine.search(name, mode="keyword", max_results=50)

        # Filter for name matches
        matches = [
            {
                "title": r.conversation_name,
                "path": str(r.file_path),
                "score": r.score,
            }
            for r in results
            if name.lower() in r.conversation_name.lower()
        ]

        return matches

    def search_with_context(
        self,
        query: str,
        context_length: int = 500
    ) -> list[dict[str, Any]]:
        """
        Search and return results with extended context.

        Args:
            query: Search query
            context_length: Characters of context to include

        Returns:
            List of results with extended snippets
        """
        results = self.engine.search(query, mode="hybrid", max_results=10)

        # Extend snippet length
        return [
            {
                "title": r.conversation_name,
                "score": round(r.score, 3),
                "context": r.snippet[:context_length],
                "path": str(r.file_path),
            }
            for r in results
        ]


def example_usage():
    """Demonstrate API usage in a custom application."""
    # Initialize API
    api = ConversationSearchAPI()

    print("Claude Search API Integration Example")
    print("=" * 70)

    # Example 1: Quick search
    print("\n1. Quick Search:")
    results = api.quick_search("database optimization", limit=3)
    for i, result in enumerate(results, 1):
        print(f"{i}. {result['title']} (score: {result['score']})")
        print(f"   {result['snippet'][:100]}...")

    # Example 2: Search by specific mode
    print("\n2. Semantic Search:")
    results = api.search_by_mode("how to improve code quality", mode="semantic", limit=3)
    for i, result in enumerate(results, 1):
        print(f"{i}. {result.conversation_name} (score: {result.score:.3f})")

    # Example 3: Find conversation by name
    print("\n3. Find Conversation by Name:")
    matches = api.get_conversation_by_name("refactor")
    for match in matches[:3]:
        print(f"   - {match['title']}")

    # Example 4: Extended context
    print("\n4. Search with Extended Context:")
    results = api.search_with_context("error handling", context_length=200)
    for i, result in enumerate(results[:2], 1):
        print(f"{i}. {result['title']}")
        print(f"   Context: {result['context'][:150]}...")


class CustomSearchWorkflow:
    """
    Example custom workflow integrating search into a larger application.
    """

    def __init__(self):
        self.api = ConversationSearchAPI()

    def find_related_conversations(self, topic: str) -> dict[str, Any]:
        """
        Find conversations related to a topic and provide analysis.

        Returns:
            Analysis dict with results and metadata
        """
        results = self.api.quick_search(topic, limit=20)

        return {
            "topic": topic,
            "total_found": len(results),
            "top_result": results[0] if results else None,
            "average_score": sum(r["score"] for r in results) / len(results) if results else 0,
            "all_results": results,
        }

    def compare_topics(self, topic1: str, topic2: str) -> dict[str, Any]:
        """Compare search results for two topics."""
        results1 = self.api.quick_search(topic1, limit=10)
        results2 = self.api.quick_search(topic2, limit=10)

        return {
            "topic1": {
                "name": topic1,
                "count": len(results1),
                "top_score": results1[0]["score"] if results1 else 0,
            },
            "topic2": {
                "name": topic2,
                "count": len(results2),
                "top_score": results2[0]["score"] if results2 else 0,
            },
        }


def example_workflow():
    """Demonstrate custom workflow integration."""
    print("\n\nCustom Workflow Example")
    print("=" * 70)

    workflow = CustomSearchWorkflow()

    # Analyze a topic
    analysis = workflow.find_related_conversations("testing strategies")
    print(f"\nTopic: {analysis['topic']}")
    print(f"Found: {analysis['total_found']} conversations")
    print(f"Average relevance: {analysis['average_score']:.3f}")

    if analysis['top_result']:
        print(f"Top result: {analysis['top_result']['title']}")

    # Compare topics
    comparison = workflow.compare_topics("python", "typescript")
    print(f"\nTopic Comparison:")
    print(f"  {comparison['topic1']['name']}: {comparison['topic1']['count']} results")
    print(f"  {comparison['topic2']['name']}: {comparison['topic2']['count']} results")


def main():
    """Run all API integration examples."""
    example_usage()
    example_workflow()


if __name__ == "__main__":
    main()
