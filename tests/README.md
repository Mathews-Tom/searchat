# Searchat Test Suite

This directory contains the test suite for searchat, featuring automated mocking of heavy dependencies (TensorFlow, CUDA) to enable fast, isolated testing without external requirements.

## Quick Start

### Installation

```bash
# Install test dependencies
uv pip install -e ".[test]"

# Or using pip
pip install -e ".[test]"
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=searchat --cov-report=html
open htmlcov/index.html

# Run specific test file
pytest tests/test_indexer.py

# Run specific test
pytest tests/test_indexer.py::test_process_conversation_basic

# Run with verbose output
pytest -v
```

## Test Organization

```
tests/
├── conftest.py              # Pytest configuration and shared fixtures
├── test_chunking.py         # Text chunking tests
├── test_incremental.py      # Incremental indexing tests
├── test_indexer.py          # Conversation indexing tests
├── test_query_parser.py     # Query parsing tests
├── test_platform_utils.py   # Platform detection tests
├── api/                     # API endpoint tests (120+ tests)
│   ├── test_search_routes.py
│   ├── test_conversations_routes.py
│   ├── test_chat_rag_routes.py
│   ├── test_patterns_routes.py
│   ├── test_agent_config.py
│   ├── test_stats_backup_routes.py
│   ├── test_indexing_admin_routes.py
│   ├── test_bookmarks_routes.py
│   ├── test_dashboards_routes.py
│   ├── test_analytics_routes.py
│   └── ...                  # 27 test files total
└── unit/                    # Unit tests
    ├── services/            # Service unit tests
    ├── config/              # Config unit tests
    ├── core/                # Core logic tests
    ├── models/              # Model unit tests
    ├── llm/                 # LLM service tests
    ├── mcp/                 # MCP tool tests
    ├── perf/                # Performance tests
    └── daemon/              # Daemon tests
```

## Test Categories

Tests are categorized using pytest markers:

### Unit Tests
Fast, isolated tests with mocked dependencies:
```bash
pytest -m unit
```

### Integration Tests
Tests that verify component interactions:
```bash
pytest -m integration
```

### Slow Tests
Tests that take >1 second:
```bash
# Run fast tests only
pytest -m "not slow"

# Run slow tests only
pytest -m slow
```

### Benchmark Tests
Performance benchmarks:
```bash
pytest -m benchmark
```

## Mocking Infrastructure

The test suite uses automatic mocking to avoid heavy dependencies:

### Sentence Transformers (TensorFlow)
- **Problem**: `sentence-transformers` imports `tf_keras`, requiring TensorFlow installation
- **Solution**: Mock at import time in `conftest.py`
- **Coverage**: Returns fake 384-dimensional embeddings

### FAISS
- **Problem**: FAISS requires system libraries and optionally GPU support
- **Solution**: Mock `faiss` module with in-memory index
- **Coverage**: Provides fake search results

### How It Works

Mocks are injected into `sys.modules` at import time (before any searchat imports):

```python
# tests/conftest.py
import sys
from unittest.mock import MagicMock

# Mock sentence-transformers before any imports
mock_st_module = MagicMock()
sys.modules['sentence_transformers'] = mock_st_module

# Now imports work without TensorFlow
from searchat.indexer import ConversationIndexer  # ✓ Works!
```

## Shared Fixtures

Common fixtures available in all tests (defined in `conftest.py`):

### `temp_searchat_dir`
Creates temporary `.searchat` directory structure:
```python
def test_example(temp_searchat_dir):
    # temp_searchat_dir = Path to temporary .searchat/
    assert temp_searchat_dir.exists()
    assert (temp_searchat_dir / "data" / "conversations").exists()
```

### `test_config`
Provides test configuration with all required sections:
```python
def test_example(test_config):
    assert test_config.embedding.model == 'all-MiniLM-L6-v2'
    assert test_config.search.default_mode == 'hybrid'
```

### `sample_conversation`
Sample conversation dict for testing:
```python
def test_example(sample_conversation):
    assert sample_conversation['conversation_id'] == 'test-conv-001'
    assert len(sample_conversation['messages']) == 2
```

### `sample_jsonl_conversation`
Creates temporary JSONL file with correct format:
```python
def test_example(sample_jsonl_conversation):
    # sample_jsonl_conversation = Path to temp JSONL file
    assert sample_jsonl_conversation.exists()
```

### `mock_embedder`
Mock embedding model:
```python
def test_example(mock_embedder):
    embeddings = mock_embedder.encode(["test"])
    assert embeddings.shape == (1, 384)
```

## Coverage

Current coverage: ~**23%** (840+ tests, expanding coverage)

### Coverage Reports

```bash
# Terminal summary
pytest --cov=searchat --cov-report=term-missing

# HTML report (detailed)
pytest --cov=searchat --cov-report=html
open htmlcov/index.html

# XML report (for CI)
pytest --cov=searchat --cov-report=xml
```

### Coverage by Module

> Note: Module coverage numbers below are from v0.5.0. Coverage is being expanded with each release.

| Module | Coverage | Status |
|--------|----------|--------|
| `models.py` | 100% | ✓ Excellent |
| `constants.py` | 100% | ✓ Excellent |
| `__init__.py` | 100% | ✓ Excellent |
| `config.py` | 90% | ✓ Good |
| `query_parser.py` | 85% | ✓ Good |
| `path_resolver.py` | 59% | ⚠ Needs improvement |
| `progress.py` | 51% | ⚠ Needs improvement |
| `indexer.py` | 25% | ⚠ Needs improvement |
| `search_engine.py` | 10% | ⚠ Needs improvement |
| `cli.py` | 0% | ✗ No coverage |
| `web_api.py` | 0% | ✗ No coverage |

## Writing Tests

### Basic Test Structure

```python
def test_example(temp_searchat_dir, test_config):
    """Test description."""
    # Arrange: Set up test data
    indexer = ConversationIndexer(temp_searchat_dir, test_config)

    # Act: Execute the operation
    result = indexer.some_method()

    # Assert: Verify the outcome
    assert result is not None
    assert result.property == expected_value
```

### Test Data Format

JSONL conversations must use the correct format:

```python
# ✓ Correct format
conversation = {
    "type": "user",
    "message": {"content": "Hello"},  # Use "content", not "text"
    "timestamp": "2026-01-20T10:00:00Z",
    "uuid": "msg-001"
}

# ✗ Wrong format
conversation = {
    "type": "user",
    "message": {"text": "Hello"},  # Wrong: "text" instead of "content"
    "timestamp": "2026-01-20T10:00:00Z"
}
```

### Adding Test Markers

```python
import pytest

@pytest.mark.unit
def test_fast():
    """Fast unit test with mocks."""
    assert True

@pytest.mark.integration
def test_components():
    """Integration test."""
    assert True

@pytest.mark.slow
def test_expensive_operation():
    """Slow test >1s."""
    assert True
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install uv
          uv pip install -e ".[test]"

      - name: Run tests
        run: pytest --cov=searchat --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

## Troubleshooting

### Import Errors

**Problem**: `ModuleNotFoundError: No module named 'tf_keras'`

**Solution**: Mocks should be defined in `conftest.py` before any imports. If you see this error, mocking failed.

**Check**:
```python
# conftest.py should have this at the top (before any searchat imports)
import sys
sys.modules['sentence_transformers'] = mock_st_module
```

### Test Failures

**Problem**: Tests fail with empty content

**Solution**: Check JSONL format. Use `"content"` not `"text"` in message objects.

### Coverage Below Threshold

**Problem**: `FAIL Required test coverage of 25% not reached`

**Solution**: Current threshold is 25%. To adjust:
```ini
# pytest.ini
[pytest]
addopts = --cov-fail-under=25
```

### Flaky Tests

**Problem**: Tests pass sometimes but fail other times

**Solution**:
1. Check for shared state between tests
2. Use fixtures to ensure clean state
3. Run tests multiple times: `pytest --count=10`

## Performance

### Test Execution Time

- **Total**: ~5s for 840+ tests
- **Per test**: ~6ms average
- **No external dependencies**: All heavy deps mocked

### Optimization Tips

```bash
# Run tests in parallel (requires pytest-xdist)
pytest -n auto

# Run only fast tests
pytest -m "not slow"

# Skip coverage for faster runs
pytest --no-cov
```

## Future Improvements

### Coverage Goals
- Increase overall coverage from 23% to 40%
- Add tests for `cli.py` (currently 0%)
- Add tests for `search_engine.py` (currently 10%)
- Expand pattern mining and agent config test coverage

### New Test Categories
- End-to-end tests for full indexing + search workflow
- Property-based tests using Hypothesis
- Performance regression tests
- Load tests for large datasets

### Infrastructure
- Add mutation testing (e.g., mutmut)
- Set up test containers for integration tests
- Add visual regression testing for web UI

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [Searchat implementation plan](.docs/IMPLEMENTATION_PLAN.md)

## Questions?

If you have questions about the test suite, check:
1. This README
2. `conftest.py` for fixture definitions
3. Existing tests for examples
4. Implementation plan for test strategy
