import pytest
from searchat.core import QueryParser


def test_parse_simple_query():
    parser = QueryParser()
    result = parser.parse("machine learning")
    
    assert result.original == "machine learning"
    assert len(result.should_include) > 0


def test_parse_must_include():
    parser = QueryParser()
    result = parser.parse("+python +tensorflow")
    
    assert "python" in result.must_include
    assert "tensorflow" in result.must_include


def test_parse_must_exclude():
    parser = QueryParser()
    result = parser.parse("python -java")
    
    assert "java" in result.must_exclude


def test_parse_exact_phrase():
    parser = QueryParser()
    result = parser.parse('"machine learning"')
    
    assert "machine learning" in result.exact_phrases


def test_parse_complex_query():
    parser = QueryParser()
    result = parser.parse('+python "neural network" -java')

    assert "python" in result.must_include
    assert "neural network" in result.exact_phrases
    assert "java" in result.must_exclude


def test_parse_and_operator():
    parser = QueryParser()
    result = parser.parse("python AND tensorflow")
    assert "python" in result.must_include
    assert "tensorflow" in result.must_include


def test_parse_or_operator():
    parser = QueryParser()
    result = parser.parse("python OR javascript")
    assert "python" in result.should_include
    assert "javascript" in result.should_include


def test_date_filter_today():
    parser = QueryParser()
    result = parser.parse("errors today")
    assert result.date_filter is not None
    assert result.date_filter.from_date.hour == 0


def test_date_filter_last_week():
    parser = QueryParser()
    result = parser.parse("bugs last week")
    assert result.date_filter is not None


def test_date_filter_last_30_days():
    parser = QueryParser()
    result = parser.parse("deployment last 30 days")
    assert result.date_filter is not None


def test_date_filter_last_3_months():
    parser = QueryParser()
    result = parser.parse("refactor last 3 months")
    assert result.date_filter is not None


def test_no_date_filter():
    parser = QueryParser()
    result = parser.parse("simple query")
    assert result.date_filter is None