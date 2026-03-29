"""Tests for the query classifier."""
from __future__ import annotations

import pytest

from searchat.core.query_classifier import (
    QueryCategory,
    QueryClassifier,
    QueryWeights,
)


class TestQueryWeights:
    def test_weights_must_sum_to_one(self) -> None:
        with pytest.raises(ValueError, match="must sum to 1.0"):
            QueryWeights(keyword_weight=0.5, semantic_weight=0.3, category=QueryCategory.CODE)

    def test_valid_weights(self) -> None:
        w = QueryWeights(keyword_weight=0.8, semantic_weight=0.2, category=QueryCategory.CODE)
        assert w.keyword_weight == 0.8
        assert w.semantic_weight == 0.2


class TestQueryClassifier:
    @pytest.fixture()
    def classifier(self) -> QueryClassifier:
        return QueryClassifier()

    def test_empty_query_returns_keyword_only(self, classifier: QueryClassifier) -> None:
        w = classifier.classify("")
        assert w.keyword_weight == 1.0
        assert w.semantic_weight == 0.0
        assert w.category == QueryCategory.SHORT

    def test_wildcard_query_returns_keyword_only(self, classifier: QueryClassifier) -> None:
        w = classifier.classify("*")
        assert w.keyword_weight == 1.0
        assert w.semantic_weight == 0.0

    def test_short_query_balanced(self, classifier: QueryClassifier) -> None:
        w = classifier.classify("auth")
        assert w.category == QueryCategory.SHORT
        assert w.keyword_weight == 0.5
        assert w.semantic_weight == 0.5

    def test_code_query_high_keyword_weight(self, classifier: QueryClassifier) -> None:
        w = classifier.classify("def parse_config function error")
        assert w.category == QueryCategory.CODE
        assert w.keyword_weight >= 0.7

    def test_conceptual_query_high_semantic_weight(self, classifier: QueryClassifier) -> None:
        w = classifier.classify("how does the authentication system work in this project")
        assert w.category == QueryCategory.CONCEPTUAL
        assert w.semantic_weight >= 0.6

    def test_navigational_query(self, classifier: QueryClassifier) -> None:
        w = classifier.classify("where is the config file located")
        assert w.category == QueryCategory.NAVIGATIONAL

    def test_factual_query(self, classifier: QueryClassifier) -> None:
        w = classifier.classify("what version of python are we using")
        assert w.category == QueryCategory.FACTUAL

    def test_code_patterns_detected(self, classifier: QueryClassifier) -> None:
        # snake_case + method call pattern
        w = classifier.classify("search_engine.search() returns empty list")
        assert w.category == QueryCategory.CODE

    def test_camel_case_detected_as_code(self, classifier: QueryClassifier) -> None:
        w = classifier.classify("SearchEngine class definition implementation")
        assert w.category == QueryCategory.CODE
