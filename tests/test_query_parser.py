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