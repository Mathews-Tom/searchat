"""Search analytics service for tracking search patterns."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from searchat.config import Config


class SearchAnalyticsService:
    """Service for tracking and analyzing search queries."""

    def __init__(self, config: Config):
        """Initialize analytics service."""
        self.config = config
        self.logs_dir = Path(config.paths.search_directory) / 'analytics'
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Define schema for search logs
        self.schema = pa.schema([
            ('query', pa.string()),
            ('result_count', pa.int64()),
            ('search_mode', pa.string()),
            ('timestamp', pa.timestamp('us')),
            ('search_time_ms', pa.int64()),
        ])

    def log_search(
        self,
        query: str,
        result_count: int,
        search_mode: str,
        search_time_ms: int
    ) -> None:
        """Log a search query."""
        # Create log file path based on current date
        today = datetime.now().date()
        log_file = self.logs_dir / f"search_logs_{today.isoformat()}.parquet"

        # Create new record
        table = pa.table({
            'query': [query],
            'result_count': [result_count],
            'search_mode': [search_mode],
            'timestamp': [datetime.now()],
            'search_time_ms': [search_time_ms],
        }, schema=self.schema)

        # Append to existing file or create new one
        if log_file.exists():
            # Read existing data
            existing_table = pq.read_table(log_file)
            # Concatenate
            combined_table = pa.concat_tables([existing_table, table])
            # Write back
            pq.write_table(combined_table, log_file)
        else:
            # Write new file
            pq.write_table(table, log_file)

        # Rotate old logs
        self._rotate_old_logs()

    def _rotate_old_logs(self) -> None:
        """Delete logs older than 30 days."""
        cutoff_date = datetime.now().date() - timedelta(days=30)

        for log_file in self.logs_dir.glob("search_logs_*.parquet"):
            try:
                # Extract date from filename
                date_str = log_file.stem.replace("search_logs_", "")
                file_date = datetime.fromisoformat(date_str).date()

                if file_date < cutoff_date:
                    log_file.unlink()
            except (ValueError, OSError):
                # Skip files with invalid names or that can't be deleted
                continue

    def get_top_queries(self, limit: int = 10, days: int = 7) -> list[dict[str, Any]]:
        """Get most frequent search queries."""
        import duckdb

        # Get log files from the last N days
        cutoff_date = datetime.now().date() - timedelta(days=days)
        log_files = []

        for log_file in self.logs_dir.glob("search_logs_*.parquet"):
            try:
                date_str = log_file.stem.replace("search_logs_", "")
                file_date = datetime.fromisoformat(date_str).date()

                if file_date >= cutoff_date:
                    log_files.append(str(log_file))
            except ValueError:
                continue

        if not log_files:
            return []

        # Query with DuckDB
        con = duckdb.connect(":memory:")

        try:
            files_pattern = ", ".join([f"'{f}'" for f in log_files])

            query = f"""
                SELECT
                    query,
                    COUNT(*) as search_count,
                    AVG(result_count) as avg_results,
                    AVG(search_time_ms) as avg_time_ms
                FROM read_parquet([{files_pattern}])
                WHERE query != '' AND query != '*'
                GROUP BY query
                ORDER BY search_count DESC
                LIMIT ?
            """

            result = con.execute(query, [limit]).fetchall()

            return [
                {
                    'query': row[0],
                    'search_count': row[1],
                    'avg_results': round(row[2], 1),
                    'avg_time_ms': round(row[3], 1)
                }
                for row in result
            ]

        finally:
            con.close()

    def get_stats_summary(self, days: int = 7) -> dict[str, Any]:
        """Get summary statistics for recent searches."""
        import duckdb

        # Get log files from the last N days
        cutoff_date = datetime.now().date() - timedelta(days=days)
        log_files = []

        for log_file in self.logs_dir.glob("search_logs_*.parquet"):
            try:
                date_str = log_file.stem.replace("search_logs_", "")
                file_date = datetime.fromisoformat(date_str).date()

                if file_date >= cutoff_date:
                    log_files.append(str(log_file))
            except ValueError:
                continue

        if not log_files:
            return {
                'total_searches': 0,
                'unique_queries': 0,
                'avg_results': 0,
                'avg_time_ms': 0,
                'mode_distribution': {}
            }

        # Query with DuckDB
        con = duckdb.connect(":memory:")

        try:
            files_pattern = ", ".join([f"'{f}'" for f in log_files])

            # Get aggregated stats
            query = f"""
                SELECT
                    COUNT(*) as total_searches,
                    COUNT(DISTINCT query) as unique_queries,
                    AVG(result_count) as avg_results,
                    AVG(search_time_ms) as avg_time_ms
                FROM read_parquet([{files_pattern}])
            """

            result = con.execute(query).fetchone()

            if not result:
                return {
                    'total_searches': 0,
                    'unique_queries': 0,
                    'avg_results': 0,
                    'avg_time_ms': 0,
                    'mode_distribution': {}
                }

            # Get mode distribution
            mode_query = f"""
                SELECT
                    search_mode,
                    COUNT(*) as count
                FROM read_parquet([{files_pattern}])
                GROUP BY search_mode
            """

            mode_result = con.execute(mode_query).fetchall()
            mode_distribution = {row[0]: row[1] for row in mode_result}

            return {
                'total_searches': result[0] if result[0] else 0,
                'unique_queries': result[1] if result[1] else 0,
                'avg_results': round(result[2], 1) if result[2] else 0,
                'avg_time_ms': round(result[3], 1) if result[3] else 0,
                'mode_distribution': mode_distribution
            }

        finally:
            con.close()

    def get_dead_end_queries(self, limit: int = 10, days: int = 7) -> list[dict[str, Any]]:
        """Get queries that returned no or few results (dead ends)."""
        import duckdb

        # Get log files from the last N days
        cutoff_date = datetime.now().date() - timedelta(days=days)
        log_files = []

        for log_file in self.logs_dir.glob("search_logs_*.parquet"):
            try:
                date_str = log_file.stem.replace("search_logs_", "")
                file_date = datetime.fromisoformat(date_str).date()

                if file_date >= cutoff_date:
                    log_files.append(str(log_file))
            except ValueError:
                continue

        if not log_files:
            return []

        # Query with DuckDB
        con = duckdb.connect(":memory:")

        try:
            files_pattern = ", ".join([f"'{f}'" for f in log_files])

            query = f"""
                SELECT
                    query,
                    COUNT(*) as search_count,
                    AVG(result_count) as avg_results
                FROM read_parquet([{files_pattern}])
                WHERE result_count <= 3 AND query != '' AND query != '*'
                GROUP BY query
                ORDER BY search_count DESC
                LIMIT ?
            """

            result = con.execute(query, [limit]).fetchall()

            return [
                {
                    'query': row[0],
                    'search_count': row[1],
                    'avg_results': round(row[2], 1)
                }
                for row in result
            ]

        finally:
            con.close()
