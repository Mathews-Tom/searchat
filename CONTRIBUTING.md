# Contributing to Searchat

## Development Setup

### Prerequisites

- Python 3.10 or higher
- Git
- Virtual environment tool (venv, conda, etc.)

### Initial Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/Process-Point-Technologies-Corporation/searchat.git
   cd searchat
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv

   # Windows
   .venv\Scripts\activate

   # Unix/macOS
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -e ".[dev]"  # Install with dev dependencies
   ```

4. **Run setup**
   ```bash
   python -m searchat.setup
   ```

### Development Workflow

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write clear, documented code
   - Follow existing code style
   - Add tests for new functionality
   - Update documentation as needed

3. **Test your changes**
   ```bash
   # Run all tests
   pytest

   # Run specific test suite
   pytest tests/api/              # API endpoint tests
   pytest tests/test_indexer.py   # Indexer tests

   # Run with coverage
   pytest --cov=searchat --cov-report=html

   # Test manually
   searchat-web           # Web interface
   searchat "test query"  # CLI
   ```

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "Brief description of changes"
   ```

5. **Push and create pull request**
   ```bash
   git push origin feature/your-feature-name
   ```

## Code Style Guidelines

### Python Style

- Follow PEP 8
- Use type hints for function signatures
- Maximum line length: 100 characters
- Use docstrings for all public functions and classes

**Example:**
```python
def search_conversations(
    query: str,
    mode: SearchMode = SearchMode.HYBRID,
    max_results: int = 100
) -> list[SearchResult]:
    """
    Search conversations with the given query.

    Args:
        query: Search query string
        mode: Search mode (keyword, semantic, or hybrid)
        max_results: Maximum number of results to return

    Returns:
        List of SearchResult objects
    """
    pass
```

### Configuration

- Put magic numbers in `constants.py`
- Use environment variables for user-specific settings
- Document all configuration options

### Error Handling

- Use specific exceptions, not bare `except:`
- Provide helpful error messages
- Include recovery suggestions in error text

**Good:**
```python
if not config_file.exists():
    raise FileNotFoundError(
        f"Configuration file not found: {config_file}\n"
        f"Run 'python -m searchat.setup' to create it."
    )
```

**Bad:**
```python
try:
    load_config()
except:
    pass
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run specific test suite
pytest tests/api/                      # API endpoint tests (120+ tests)
pytest tests/test_indexer.py           # Core indexer tests

# Run specific test
pytest tests/api/test_search_routes.py::TestSearchEndpoint::test_search_mode_hybrid

# Run with coverage
pytest --cov=searchat --cov-report=html

# Exclude slow tests
pytest -m "not slow"
```

### Test Organization

```
tests/
├── conftest.py                   # Shared fixtures
├── test_*.py                     # Core unit tests
├── api/                          # API endpoint tests (120+)
│   ├── test_search_routes.py
│   ├── test_conversations_routes.py
│   ├── test_chat_rag_routes.py
│   ├── test_patterns_routes.py
│   ├── test_agent_config.py
│   ├── test_stats_backup_routes.py
│   ├── test_indexing_admin_routes.py
│   └── ...                       # 27 test files total
└── unit/                         # Unit tests
    ├── services/                 # Service tests
    ├── config/                   # Config tests
    ├── core/                     # Core logic tests
    └── ...
```

### Writing Tests

- Place unit tests in `tests/`
- Place API tests in `tests/api/`
- Name test files `test_*.py`
- Use descriptive test names explaining what's being tested
- Include both positive and negative test cases
- Mock external dependencies (SearchEngine, BackupManager)
- Use pytest fixtures from `conftest.py`

**Unit Test Example:**
```python
def test_search_returns_results():
    """Test that search returns results for valid query."""
    engine = SearchEngine(config)
    results = engine.search("test query")
    assert len(results) > 0
```

**API Test Example:**
```python
from unittest.mock import Mock, patch

def test_search_endpoint(client, mock_search_engine):
    """Test search endpoint returns results."""
    with patch('searchat.api.routers.search.get_search_engine', return_value=mock_search_engine):
        response = client.get("/api/search?q=test&mode=hybrid")

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert data["mode_used"] == "hybrid"
```

## Pull Request Process

### Before Submitting

- [ ] Code follows style guidelines
- [ ] Tests pass locally
- [ ] New tests added for new features
- [ ] Documentation updated
- [ ] Commit messages are clear
- [ ] No merge conflicts with main

### PR Description Template

```markdown
## Description
Brief description of what this PR does.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
How was this tested? What edge cases were considered?

## Checklist
- [ ] Code follows project style guidelines
- [ ] Tests pass
- [ ] Documentation updated
- [ ] No breaking changes (or documented if unavoidable)
```

### Review Process

1. Automated checks will run on your PR
2. Maintainers will review your code
3. Address any feedback or requested changes
4. Once approved, your PR will be merged

## Areas for Contribution

### High Priority

- Cross-platform testing (Windows, WSL, Linux, macOS)
- Performance optimizations
- Better error messages
- Additional search modes or filters
- Documentation improvements

### Good First Issues

Look for issues labeled `good-first-issue` in the issue tracker. These are typically:
- Documentation updates
- Small bug fixes
- Code cleanup
- Test coverage improvements

### Feature Requests

Before starting work on a major feature:
1. Check if an issue exists
2. Create an issue to discuss the feature
3. Wait for maintainer feedback
4. Proceed with implementation once approved

## Platform-Specific Testing

### Windows

```powershell
searchat-web
# Test WSL path detection
# Test UNC paths (\\wsl$\...)
```

### WSL

```bash
cd /mnt/d/projects/searchat
searchat-web
# Test Windows mount points (/mnt/c/...)
# Test path translation
```

### Linux/macOS

```bash
searchat-web
# Test standard Unix paths
# Test auto-detection
```

## Security

### Reporting Security Issues

Do NOT create public issues for security vulnerabilities. Instead:
- Open a GitHub issue with "Security" label
- Include detailed description and steps to reproduce
- Allow time for fix before public disclosure

### Security Considerations

- Never commit API keys or credentials
- Parquet files contain conversation data - exclude from git
- Test input validation and sanitization
- Consider privacy implications of search features

## Documentation

### Types of Documentation

1. **Code comments** - Explain complex logic
2. **Docstrings** - Describe function/class behavior
3. **README.md** - Quick start and overview
4. **This file** - Contribution guidelines
5. **Examples** - Working code samples

### Documentation Standards

- Use clear, simple language
- Include code examples
- Explain why, not just what
- Keep documentation up to date with code changes

## Questions?

- Open a discussion on GitHub
- Check existing issues and pull requests
- Review the examples directory
- Read the architecture documentation

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Code of Conduct

- Be respectful and professional
- Welcome newcomers
- Focus on constructive feedback
- Assume good intentions
- Help create an inclusive community
