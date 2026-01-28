# Benchmarks

Performance benchmarking scripts for measuring Searchat optimization improvements.

## Scripts

### bench_dataframe_and_embedding.py
Measures DataFrame and embedding optimization improvements:
- **Conversation lookups**: O(n) filter vs O(1) index lookup
- **DataFrame iteration**: iterrows() vs to_dict('records')
- **Batch encoding**: Sequential vs batch processing with SentenceTransformer
- **HTML caching**: File read vs in-memory cache

Run with:
```bash
python benchmarks/bench_dataframe_and_embedding.py
```

### bench_duckdb_query_performance.py
Measures DuckDB query performance optimizations.

Run with:
```bash
python benchmarks/bench_duckdb_query_performance.py
```

### bench_duckdb_predicate_pushdown.py
Measures predicate pushdown optimization for filtering operations in DuckDB.
Tests how DuckDB pushes WHERE clauses down to Parquet file scanning.

Run with:
```bash
python benchmarks/bench_duckdb_predicate_pushdown.py
```

### bench_duckdb_projection_pushdown.py
Measures projection pushdown optimization for column selection in DuckDB.
Tests how DuckDB reads only required columns from Parquet files.

Run with:
```bash
python benchmarks/bench_duckdb_projection_pushdown.py
```

## Requirements

Benchmarks require the full development environment:
```bash
pip install -e ".[dev]"
```

## Notes

- Benchmarks are standalone scripts and not part of the test suite
- They measure performance characteristics, not correctness
- Results vary based on hardware (CPU, GPU availability, disk speed)
- Some benchmarks require actual data files to exist in the search index
