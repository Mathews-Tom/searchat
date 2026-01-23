# Searchat Examples

This directory contains examples demonstrating various use cases and configurations.

## Code Examples

### Basic Usage

- **`basic_search.py`** - Simple keyword search with default configuration
  ```bash
  python examples/basic_search.py
  ```

### Advanced Features

- **`advanced_search.py`** - Custom filters, date ranges, and search mode comparison
  ```bash
  python examples/advanced_search.py
  ```

- **`custom_indexing.py`** - Monitor index status and statistics (read-only)
  ```bash
  python examples/custom_indexing.py
  ```

- **`batch_operations.py`** - Bulk processing, topic analysis, and result export
  ```bash
  python examples/batch_operations.py
  ```

### Integration

- **`api_integration.py`** - Using searchat as a library in other projects
  ```bash
  python examples/api_integration.py
  ```

## Configuration Examples

Located in `config_examples/`:

### Environment Files (.env)

- **`basic_config.env`** - Minimal configuration for quick start
- **`advanced_config.env`** - Complete reference of all available options

### TOML Configuration

- **`multi_user.toml`** - Shared server setup for multiple users
- **`isolated_variants.toml`** - Running multiple variants safely

## Usage

1. Copy example files to your project directory
2. Modify paths and settings for your environment
3. Run examples directly with Python:
   ```bash
   python examples/basic_search.py
   ```

## Requirements

All examples require:
- Searchat installed (`pip install -r requirements.txt`)
- At least one indexed conversation
- Valid configuration (run `python -m searchat.setup` first)

## Notes

- Examples are safe to run and won't modify your data
- Indexing examples are read-only to protect existing indexes
- Configuration examples include detailed comments explaining each option
