from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import duckdb
import numpy as np

from searchat.config import Config


_FILENAME_DATE_RE = re.compile(r"^search_logs_(\d{4}-\d{2}-\d{2})$")


@dataclass(frozen=True)
class AnalyticsConfigSnapshot:
    enabled: bool
    retention_days: int


class SearchAnalyticsService:
    """Service for tracking and analyzing search queries."""

    def __init__(self, config: Config):
        self._config = config
        self.logs_dir = Path(config.paths.search_directory) / "analytics"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self.logs_dir / "analytics.duckdb"

        self._ensure_db()

    def config_snapshot(self) -> AnalyticsConfigSnapshot:
        return AnalyticsConfigSnapshot(
            enabled=self._config.analytics.enabled,
            retention_days=self._config.analytics.retention_days,
        )

    def log_search(
        self,
        query: str,
        result_count: int,
        search_mode: str,
        search_time_ms: int,
        *,
        tool_filter: str | None = None,
    ) -> None:
        """Log a search query (opt-in)."""

        if not self._config.analytics.enabled:
            return

        normalized_query = query.strip()
        now = datetime.now(timezone.utc)
        tool_value = (tool_filter or "all").strip().lower() or "all"

        with self._connect() as con:
            con.execute(
                """
                INSERT INTO search_history (
                    query,
                    result_count,
                    search_mode,
                    timestamp,
                    search_time_ms,
                    tool_filter
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [normalized_query, int(result_count), str(search_mode), now, int(search_time_ms), tool_value],
            )

            cutoff = now - timedelta(days=int(self._config.analytics.retention_days))
            con.execute("DELETE FROM search_history WHERE timestamp < ?", [cutoff])

        self._rotate_old_parquet_logs()

    def get_stats_summary(self, *, days: int = 7) -> dict[str, Any]:
        """Get summary statistics for recent searches."""

        cutoff = self._cutoff(days)
        with self._connect(read_only=True) as con:
            result = con.execute(
                """
                SELECT
                    COUNT(*) AS total_searches,
                    COUNT(DISTINCT query) AS unique_queries,
                    AVG(result_count) AS avg_results,
                    AVG(search_time_ms) AS avg_time_ms
                FROM search_history
                WHERE timestamp >= ?
                """,
                [cutoff],
            ).fetchone()

            if not result or result[0] is None:
                return {
                    "total_searches": 0,
                    "unique_queries": 0,
                    "avg_results": 0,
                    "avg_time_ms": 0,
                    "mode_distribution": {},
                }

            mode_rows = con.execute(
                """
                SELECT search_mode, COUNT(*) AS count
                FROM search_history
                WHERE timestamp >= ?
                GROUP BY search_mode
                """,
                [cutoff],
            ).fetchall()

        mode_distribution = {row[0]: row[1] for row in mode_rows}
        return {
            "total_searches": int(result[0] or 0),
            "unique_queries": int(result[1] or 0),
            "avg_results": round(float(result[2] or 0), 1),
            "avg_time_ms": round(float(result[3] or 0), 1),
            "mode_distribution": mode_distribution,
        }

    def get_top_queries(self, *, limit: int = 10, days: int = 7) -> list[dict[str, Any]]:
        """Get most frequent search queries."""

        cutoff = self._cutoff(days)
        with self._connect(read_only=True) as con:
            rows = con.execute(
                """
                SELECT
                    query,
                    COUNT(*) AS search_count,
                    AVG(result_count) AS avg_results,
                    AVG(search_time_ms) AS avg_time_ms
                FROM search_history
                WHERE timestamp >= ?
                  AND query != ''
                  AND query != '*'
                GROUP BY query
                ORDER BY search_count DESC
                LIMIT ?
                """,
                [cutoff, int(limit)],
            ).fetchall()

        return [
            {
                "query": row[0],
                "search_count": int(row[1]),
                "avg_results": round(float(row[2] or 0), 1),
                "avg_time_ms": round(float(row[3] or 0), 1),
            }
            for row in rows
        ]

    def get_dead_end_queries(self, *, limit: int = 10, days: int = 7) -> list[dict[str, Any]]:
        """Get queries that returned few or no results (dead ends)."""

        cutoff = self._cutoff(days)
        with self._connect(read_only=True) as con:
            rows = con.execute(
                """
                SELECT
                    query,
                    COUNT(*) AS search_count,
                    AVG(result_count) AS avg_results
                FROM search_history
                WHERE timestamp >= ?
                  AND result_count <= 3
                  AND query != ''
                  AND query != '*'
                GROUP BY query
                ORDER BY search_count DESC
                LIMIT ?
                """,
                [cutoff, int(limit)],
            ).fetchall()

        return [
            {
                "query": row[0],
                "search_count": int(row[1]),
                "avg_results": round(float(row[2] or 0), 1),
            }
            for row in rows
        ]

    def get_trends(self, *, days: int = 30) -> list[dict[str, Any]]:
        """Get daily trends for searches and latency."""

        cutoff = self._cutoff(days)
        with self._connect(read_only=True) as con:
            rows = con.execute(
                """
                SELECT
                    CAST(timestamp AS DATE) AS day,
                    COUNT(*) AS searches,
                    COUNT(DISTINCT query) AS unique_queries,
                    AVG(search_time_ms) AS avg_time_ms,
                    AVG(result_count) AS avg_results
                FROM search_history
                WHERE timestamp >= ?
                GROUP BY day
                ORDER BY day ASC
                """,
                [cutoff],
            ).fetchall()

        return [
            {
                "day": row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]),
                "searches": int(row[1]),
                "unique_queries": int(row[2]),
                "avg_time_ms": round(float(row[3] or 0), 1),
                "avg_results": round(float(row[4] or 0), 1),
            }
            for row in rows
        ]

    def get_heatmap(self, *, days: int = 30) -> dict[str, Any]:
        """Get hour-of-day x day-of-week heatmap counts."""

        cutoff = self._cutoff(days)
        with self._connect(read_only=True) as con:
            rows = con.execute(
                """
                SELECT
                    EXTRACT(dow FROM timestamp) AS dow,
                    EXTRACT(hour FROM timestamp) AS hour,
                    COUNT(*) AS searches
                FROM search_history
                WHERE timestamp >= ?
                GROUP BY dow, hour
                ORDER BY dow ASC, hour ASC
                """,
                [cutoff],
            ).fetchall()

        cells = [{"dow": int(r[0]), "hour": int(r[1]), "searches": int(r[2])} for r in rows]
        return {"days": days, "cells": cells}

    def get_agent_comparison(self, *, days: int = 30) -> list[dict[str, Any]]:
        """Compare tool-filter usage and performance."""

        cutoff = self._cutoff(days)
        with self._connect(read_only=True) as con:
            rows = con.execute(
                """
                SELECT
                    tool_filter,
                    COUNT(*) AS searches,
                    AVG(search_time_ms) AS avg_time_ms,
                    AVG(result_count) AS avg_results
                FROM search_history
                WHERE timestamp >= ?
                GROUP BY tool_filter
                ORDER BY searches DESC
                """,
                [cutoff],
            ).fetchall()

        return [
            {
                "tool_filter": row[0],
                "searches": int(row[1]),
                "avg_time_ms": round(float(row[2] or 0), 1),
                "avg_results": round(float(row[3] or 0), 1),
            }
            for row in rows
        ]

    def get_topic_clusters(self, *, days: int = 30, k: int = 8) -> list[dict[str, Any]]:
        """Cluster queries into k topics using a lightweight TF-IDF + k-means."""

        if k < 2 or k > 20:
            raise ValueError("k must be between 2 and 20")

        cutoff = self._cutoff(days)
        with self._connect(read_only=True) as con:
            rows = con.execute(
                """
                SELECT query, COUNT(*) AS count
                FROM search_history
                WHERE timestamp >= ?
                  AND query != ''
                  AND query != '*'
                GROUP BY query
                ORDER BY count DESC
                """,
                [cutoff],
            ).fetchall()

        if len(rows) < k:
            return []

        queries = [r[0] for r in rows]
        weights = np.array([int(r[1]) for r in rows], dtype=np.float64)

        vectors, vocab = _tfidf_vectors(queries)
        if vectors.shape[0] < k or vectors.shape[1] == 0:
            return []

        labels, centroids = _kmeans(vectors, k=k)

        clusters: list[dict[str, Any]] = []
        for cluster_id in range(k):
            idxs = np.where(labels == cluster_id)[0]
            if idxs.size == 0:
                continue

            cluster_queries = [queries[i] for i in idxs]
            cluster_weights = weights[idxs]
            size = int(cluster_weights.sum())

            centroid = centroids[cluster_id]
            rep_idx = int(idxs[np.argmax(vectors[idxs] @ centroid)])
            representative_query = queries[rep_idx]

            top_terms = _top_terms_for_cluster(centroid, vocab, limit=5)

            clusters.append(
                {
                    "cluster_id": cluster_id,
                    "searches": size,
                    "representative_query": representative_query,
                    "top_terms": top_terms,
                    "examples": cluster_queries[:5],
                }
            )

        clusters.sort(key=lambda c: c["searches"], reverse=True)
        return clusters

    def _cutoff(self, days: int) -> datetime:
        return datetime.now(timezone.utc) - timedelta(days=int(days))

    def _ensure_db(self) -> None:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS search_history (
                    query TEXT,
                    result_count BIGINT,
                    search_mode TEXT,
                    timestamp TIMESTAMP,
                    search_time_ms BIGINT,
                    tool_filter TEXT
                )
                """
            )

    def _connect(self, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
        if read_only:
            return duckdb.connect(str(self._db_path), read_only=True)
        return duckdb.connect(str(self._db_path))

    def _rotate_old_parquet_logs(self) -> None:
        """Remove legacy parquet logs older than the retention window."""

        retention_days = int(self._config.analytics.retention_days)
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=retention_days)).date()
        for log_file in self.logs_dir.glob("search_logs_*.parquet"):
            match = _FILENAME_DATE_RE.match(log_file.stem)
            if not match:
                continue

            try:
                file_date = datetime.fromisoformat(match.group(1)).date()
            except ValueError:
                continue

            if file_date < cutoff_date:
                try:
                    log_file.unlink()
                except OSError:
                    continue


_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "what",
    "when",
    "where",
    "why",
    "with",
}


def _tokenize(text: str) -> list[str]:
    tokens = _TOKEN_RE.findall(text.lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) >= 2]


def _tfidf_vectors(queries: list[str]) -> tuple[np.ndarray, list[str]]:
    token_lists = [_tokenize(q) for q in queries]
    df: dict[str, int] = {}
    for tokens in token_lists:
        for t in set(tokens):
            df[t] = df.get(t, 0) + 1

    vocab = [t for t, _ in sorted(df.items(), key=lambda kv: (-kv[1], kv[0]))[:512]]
    vocab_index = {t: i for i, t in enumerate(vocab)}

    n = len(queries)
    m = len(vocab)
    if m == 0:
        return np.zeros((n, 0), dtype=np.float64), []

    idf = np.zeros(m, dtype=np.float64)
    for t, i in vocab_index.items():
        idf[i] = np.log((1 + n) / (1 + df.get(t, 0))) + 1.0

    x = np.zeros((n, m), dtype=np.float64)
    for row_idx, tokens in enumerate(token_lists):
        if not tokens:
            continue
        tf: dict[str, int] = {}
        for t in tokens:
            if t in vocab_index:
                tf[t] = tf.get(t, 0) + 1
        if not tf:
            continue
        max_tf = max(tf.values())
        for t, c in tf.items():
            col = vocab_index[t]
            x[row_idx, col] = (c / max_tf) * idf[col]

    norms = np.linalg.norm(x, axis=1)
    norms[norms == 0] = 1.0
    x = x / norms[:, None]
    return x, vocab


def _kmeans(x: np.ndarray, *, k: int, max_iter: int = 25, seed: int = 7) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    n = x.shape[0]

    centroids = x[rng.choice(n, size=k, replace=False)].copy()
    labels = np.zeros(n, dtype=np.int64)

    for _ in range(max_iter):
        sim = x @ centroids.T
        new_labels = np.argmax(sim, axis=1)
        if np.array_equal(new_labels, labels):
            break
        labels = new_labels

        for cluster_id in range(k):
            idxs = np.where(labels == cluster_id)[0]
            if idxs.size == 0:
                centroids[cluster_id] = x[rng.integers(0, n)]
                continue
            c = x[idxs].mean(axis=0)
            norm = np.linalg.norm(c)
            centroids[cluster_id] = c if norm == 0 else (c / norm)

    return labels, centroids


def _top_terms_for_cluster(centroid: np.ndarray, vocab: list[str], *, limit: int) -> list[str]:
    if centroid.size == 0:
        return []
    idxs = np.argsort(-centroid)[:limit]
    return [vocab[int(i)] for i in idxs if centroid[int(i)] > 0]
