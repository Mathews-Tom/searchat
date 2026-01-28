# Benchmarks

Performance benchmarking scripts for measuring Searchat optimization improvements.

## Scripts

### benchmark_optimizations.py
Measures Phase 1 optimization improvements comparing old vs new approaches:
- **Conversation lookups**: O(n) filter vs O(1) index lookup
- **DataFrame iteration**: iterrows() vs to_dict('records')
- **Batch encoding**: Sequential vs batch processing with SentenceTransformer
- **HTML caching**: File read vs in-memory cache

Run with:
```bash
python benchmarks/benchmark_optimizations.py
```

### benchmark_phase2.py
Measures Phase 2 DuckDB query optimizations.

Run with:
```bash
python benchmarks/benchmark_phase2.py
```

### benchmark_predicate_pushdown.py
Measures predicate pushdown optimization for filtering operations in DuckDB.

Run with:
```bash
python benchmarks/benchmark_predicate_pushdown.py
```

### benchmark_projection_pushdown.py
Measures projection pushdown optimization for column selection in DuckDB.

Run with:
```bash
python benchmarks/benchmark_projection_pushdown.py
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
