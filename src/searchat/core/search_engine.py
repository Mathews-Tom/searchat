from __future__ import annotations

import json
import logging
import time
import hashlib
from collections import defaultdict, OrderedDict
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Any, cast
import duckdb
import faiss
import numpy as np

from searchat.core.filters import tool_sql_conditions
from searchat.models import (
    SearchMode,
    SearchFilters,
    SearchResult,
    SearchResults,
)
from searchat.core.query_parser import QueryParser
from searchat.config import Config
from searchat.config.constants import (
    INDEX_SCHEMA_VERSION,
    INDEX_FORMAT_VERSION,
    INDEX_FORMAT,
    INDEX_METADATA_FILENAME,
    FTS_STEMMER,
    FTS_STOPWORDS,
    QUERY_SYNONYMS,
)


if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


class SearchEngine:
    def __init__(self, search_dir: Path, config: Config | None = None):
        self.search_dir = search_dir
        self.faiss_index: faiss.Index | None = None
        self.embedder: SentenceTransformer | None = None
        self.query_parser = QueryParser()

        self._init_lock = Lock()
        
        if config is None:
            config = Config.load()
        self.config = config
        
        self.conversations_dir = self.search_dir / "data" / "conversations"
        self.metadata_path = self.search_dir / "data" / "indices" / "embeddings.metadata.parquet"
        self.index_path = self.search_dir / "data" / "indices" / "embeddings.faiss"
        self.conversations_glob = str(self.conversations_dir / "*.parquet")

        # LRU cache for search results
        self.cache_size = config.performance.query_cache_size
        self.result_cache: OrderedDict[str, tuple[SearchResults, float]] = OrderedDict()
        self.cache_ttl = 300  # 5 minutes TTL

        # Columns needed for search (exclude large 'messages' column)
        self.search_columns = [
            "conversation_id",
            "project_id",
            "file_path",
            "title",
            "created_at",
            "updated_at",
            "message_count",
            "full_text",
            "embedding_id",
            "file_hash",
            "indexed_at",
        ]

        # Keyword search only depends on conversation parquets.
        self._validate_keyword_files()

        # Persistent DuckDB connection (thread-safe for reads)
        self._con = duckdb.connect(database=":memory:")
        self._logger = logging.getLogger(__name__)
        try:
            mem_mb = int(config.performance.memory_limit_mb)
            self._con.execute(f"PRAGMA memory_limit='{mem_mb}MB'")
        except Exception as exc:
            self._logger.warning("Failed to set DuckDB memory limit: %s", exc)

        # Reranker (lazy loaded)
        self._reranker = None

        # Build persistent table + FTS index (best-effort at init)
        self._fts_ready = False
        try:
            self._build_fts_table()
            self._fts_ready = True
        except Exception as exc:
            self._logger.warning("FTS table init deferred: %s", exc)
    
    def ensure_metadata_ready(self) -> None:
        """Ensure index metadata parquet exists and matches config."""
        with self._init_lock:
            self._ensure_metadata_ready_locked()


    def ensure_faiss_loaded(self) -> None:
        """Ensure FAISS index is loaded."""
        with self._init_lock:
            self._ensure_faiss_loaded_locked()


    def ensure_embedder_loaded(self) -> None:
        """Ensure sentence-transformers model is loaded."""
        with self._init_lock:
            self._ensure_embedder_loaded_locked()


    def ensure_semantic_ready(self) -> None:
        """Ensure semantic components (metadata, FAISS, embedder) are loaded."""
        with self._init_lock:
            self._ensure_metadata_ready_locked()
            self._ensure_faiss_loaded_locked()
            self._ensure_embedder_loaded_locked()


    def _ensure_metadata_ready_locked(self) -> None:
        self._validate_keyword_files()
        self._validate_index_metadata()

        if not self.metadata_path.exists():
            raise FileNotFoundError(
                f"Metadata parquet not found at {self.metadata_path}. Run indexer first."
            )


    def _ensure_faiss_loaded_locked(self) -> None:
        self._ensure_metadata_ready_locked()

        if not self.index_path.exists():
            raise FileNotFoundError(
                f"FAISS index not found at {self.index_path}. Run indexer first."
            )

        if self.faiss_index is None:
            if getattr(self.config.performance, "faiss_mmap", False):
                try:
                    flags = faiss.IO_FLAG_MMAP | faiss.IO_FLAG_READ_ONLY
                except Exception as e:
                    raise RuntimeError("FAISS mmap flags are not supported by this build") from e
                self.faiss_index = faiss.read_index(str(self.index_path), flags)
            else:
                self.faiss_index = faiss.read_index(str(self.index_path))


    def _ensure_embedder_loaded_locked(self) -> None:
        self._validate_index_metadata()

        if self.embedder is None:
            device = self.config.embedding.get_device()
            from sentence_transformers import SentenceTransformer

            self.embedder = SentenceTransformer(self.config.embedding.model, device=device)


    def refresh_index(self) -> None:
        """Clear caches and rebuild DuckDB table + FTS index."""
        with self._init_lock:
            self.result_cache.clear()
            self.faiss_index = None
            try:
                self._build_fts_table()
                self._fts_ready = True
            except Exception as exc:
                self._fts_ready = False
                self._logger.warning("FTS table rebuild failed: %s", exc)


    def _validate_keyword_files(self) -> None:
        if not self.conversations_dir.exists() or not any(self.conversations_dir.glob("*.parquet")):
            raise FileNotFoundError(f"No conversation parquet files found in {self.conversations_dir}")

    def _build_fts_table(self) -> None:
        """Create persistent DuckDB table from parquet and build FTS index.

        Deduplicates on conversation_id (keeps the most recently updated
        row) so that FTS match_bm25 scalar lookups never encounter
        multiple rows for the same key.
        """
        cols = ", ".join(self.search_columns)
        self._con.execute(f"""
            CREATE OR REPLACE TABLE conversations AS
            SELECT {cols}
            FROM parquet_scan('{self.conversations_glob}')
            QUALIFY row_number() OVER (
                PARTITION BY conversation_id ORDER BY updated_at DESC NULLS LAST
            ) = 1
        """)
        self._con.execute("INSTALL fts; LOAD fts;")
        self._con.execute(f"""
            PRAGMA create_fts_index(
                'conversations',
                'conversation_id',
                'full_text', 'title',
                stemmer='{FTS_STEMMER}',
                stopwords='{FTS_STOPWORDS}',
                overwrite=1
            )
        """)

    def close(self) -> None:
        """Close the persistent DuckDB connection."""
        if self._con:
            self._con.close()

    def _where_from_filters(
        self,
        filters: SearchFilters | None,
        params: list[object],
        *,
        table_alias: str = "",
    ) -> str:
        prefix = f"{table_alias}." if table_alias else ""
        conditions = [f"{prefix}message_count > 0"]

        if filters:
            if filters.project_ids:
                placeholders = ",".join(["?"] * len(filters.project_ids))
                conditions.append(f"{prefix}project_id IN ({placeholders})")
                params.extend(filters.project_ids)

            if filters.tool:
                conditions.extend(tool_sql_conditions(filters.tool, prefix=table_alias))

            if filters.date_from:
                conditions.append(f"{prefix}updated_at >= ?")
                params.append(filters.date_from)

            if filters.date_to:
                conditions.append(f"{prefix}updated_at <= ?")
                params.append(filters.date_to)

            if filters.min_messages > 0:
                conditions.append(f"{prefix}message_count >= ?")
                params.append(int(filters.min_messages))

        return " AND ".join(conditions)
    
    def _validate_index_metadata(self) -> None:
        metadata_path = self.search_dir / f"data/indices/{INDEX_METADATA_FILENAME}"
        
        if not metadata_path.exists():
            raise FileNotFoundError(
                f"Index metadata not found at {metadata_path}. "
                "Index format outdated, rebuild required. Run indexer."
            )
        
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        if metadata.get("embedding_model") != self.config.embedding.model:
            raise ValueError(
                f"Model mismatch: index uses '{metadata.get('embedding_model')}', "
                f"config specifies '{self.config.embedding.model}'. "
                "Rebuild index with correct model."
            )

        if metadata.get("format") != INDEX_FORMAT:
            raise ValueError(
                f"Index format mismatch: index uses '{metadata.get('format')}', "
                f"expected '{INDEX_FORMAT}'. Rebuild index required."
            )

        if metadata.get("schema_version") != INDEX_SCHEMA_VERSION:
            raise ValueError(
                f"Schema version mismatch: index uses version {metadata.get('schema_version')}, "
                f"expected version {INDEX_SCHEMA_VERSION}. Rebuild index required."
            )

        if metadata.get("index_format_version") != INDEX_FORMAT_VERSION:
            raise ValueError(
                f"Index format version mismatch: index uses version {metadata.get('index_format_version')}, "
                f"expected version {INDEX_FORMAT_VERSION}. Rebuild index required."
            )
    
    def _get_cache_key(self, query: str, mode: SearchMode, filters: SearchFilters | None) -> str:
        """Generate a cache key for the search query"""
        key_parts = [query, mode.value]
        if filters:
            if filters.project_ids:
                key_parts.append(f"projects:{','.join(filters.project_ids)}")
            if filters.date_from:
                key_parts.append(f"from:{filters.date_from.isoformat()}")
            if filters.date_to:
                key_parts.append(f"to:{filters.date_to.isoformat()}")
            if filters.min_messages > 0:
                key_parts.append(f"min_msgs:{filters.min_messages}")
        
        key_str = '|'.join(key_parts)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _get_from_cache(self, cache_key: str) -> SearchResults | None:
        """Get results from cache if valid"""
        if cache_key in self.result_cache:
            result, timestamp = self.result_cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                # Move to end (most recently used)
                self.result_cache.move_to_end(cache_key)
                return result
            else:
                # Expired, remove from cache
                del self.result_cache[cache_key]
        return None
    
    def _add_to_cache(self, cache_key: str, result: SearchResults) -> None:
        """Add results to cache with LRU eviction"""
        # Remove oldest if cache is full
        if len(self.result_cache) >= self.cache_size:
            self.result_cache.popitem(last=False)
        
        self.result_cache[cache_key] = (result, time.time())
    
    def search(
        self, 
        query: str, 
        mode: SearchMode = SearchMode.HYBRID,
        filters: SearchFilters | None = None
    ) -> SearchResults:
        start_time = time.time()

        # Treat wildcard query as keyword-only browsing.
        if query.strip() == "*" and mode != SearchMode.KEYWORD:
            mode = SearchMode.KEYWORD
        
        # Check cache first
        cache_key = self._get_cache_key(query, mode, filters)
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            # Update search time to reflect cache hit
            cached_result.search_time_ms = (time.time() - start_time) * 1000
            return cached_result
        
        try:
            if mode == SearchMode.HYBRID:
                keyword_results = self._keyword_search(query, filters)
                semantic_results = self._semantic_search(query, filters)
                results = self._merge_results(keyword_results, semantic_results)
                results = self._rerank(query, results)
            elif mode == SearchMode.KEYWORD:
                results = self._keyword_search(query, filters)
            else:
                results = self._semantic_search(query, filters)

            elapsed_ms = (time.time() - start_time) * 1000
            
            search_result = SearchResults(
                results=results,
                total_count=len(results),
                search_time_ms=elapsed_ms,
                mode_used=mode.value
            )
            
            # Add to cache
            self._add_to_cache(cache_key, search_result)
            
            return search_result
        except Exception as e:
            raise RuntimeError(f"Search failed: {e}") from e
    
    def _keyword_search(self, query: str, filters: SearchFilters | None) -> list[SearchResult]:
        if not self._fts_ready:
            try:
                self._build_fts_table()
                self._fts_ready = True
            except Exception as exc:
                self._logger.warning("FTS unavailable, keyword search returning empty: %s", exc)
                return []

        parsed = self.query_parser.parse(query)
        is_wildcard = parsed.original.strip() == "*"

        if is_wildcard:
            params: list[object] = []
            where_clause = self._where_from_filters(filters, params)
            sql = f"""
                SELECT conversation_id, project_id, title, created_at,
                       updated_at, message_count, file_path, full_text
                FROM conversations
                WHERE {where_clause}
                ORDER BY updated_at DESC
                LIMIT 100
            """
            rows = self._con.execute(sql, params).fetchall()
            return [
                SearchResult(
                    conversation_id=r[0], project_id=r[1], title=r[2],
                    created_at=r[3], updated_at=r[4], message_count=r[5],
                    file_path=r[6], score=0.0, snippet=(r[7] or "")[:200],
                )
                for r in rows
            ]

        # Expand query with synonyms
        all_terms = parsed.exact_phrases + parsed.must_include + parsed.should_include
        expanded_terms = list(all_terms)
        for term in all_terms:
            term_lower = term.lower()
            if term_lower in QUERY_SYNONYMS:
                expanded_terms.extend(QUERY_SYNONYMS[term_lower])

        # Build FTS query string
        fts_query = " ".join(expanded_terms)
        if not fts_query.strip():
            return []

        params = [fts_query]
        filter_params: list[object] = []
        where_clause = self._where_from_filters(filters, filter_params)
        params.extend(filter_params)

        # Must-exclude terms
        exclude_conditions = ""
        for term in parsed.must_exclude:
            exclude_conditions += " AND NOT (full_text ILIKE '%' || ? || '%')"
            params.append(term)

        sql = f"""
            SELECT conversation_id, project_id, title, created_at,
                   updated_at, message_count, file_path, full_text,
                   fts_main_conversations.match_bm25(conversation_id, ?) AS score
            FROM conversations
            WHERE score IS NOT NULL AND {where_clause}{exclude_conditions}
            ORDER BY score DESC
            LIMIT 100
        """
        rows = self._con.execute(sql, params).fetchall()

        if not rows:
            return []

        all_terms_lower = [t.lower() for t in all_terms]
        results: list[SearchResult] = []
        for r in rows:
            title = r[2] or ""
            title_boost = 2.0 if any(t in title.lower() for t in all_terms_lower) else 1.0
            message_boost = float(np.log1p(r[5]))
            score = float(r[8]) * title_boost * message_boost

            results.append(
                SearchResult(
                    conversation_id=r[0], project_id=r[1], title=r[2],
                    created_at=r[3], updated_at=r[4], message_count=r[5],
                    file_path=r[6], score=score,
                    snippet=self._create_snippet(r[7] or "", parsed.original),
                )
            )

        results.sort(key=lambda x: x.score, reverse=True)
        return results
    
    def _semantic_search(self, query: str, filters: SearchFilters | None) -> list[SearchResult]:
        self.ensure_faiss_loaded()
        self.ensure_embedder_loaded()
        embedder = self.embedder
        faiss_index = self.faiss_index
        if embedder is None or faiss_index is None:
            raise RuntimeError("Search engine not initialized")

        query_embedding = np.asarray(embedder.encode(query), dtype=np.float32)
        
        k = 100
        # Use the stable Python binding signature: search(x, k) -> (D, I).
        # Some FAISS index wrappers don't expose the 4-arg C++ signature.
        distances, labels = faiss_index.search(query_embedding.reshape(1, -1), k)  # type: ignore[call-arg,arg-type]
        
        valid_mask = labels[0] >= 0
        hits = []
        for vector_id, distance, order in zip(labels[0][valid_mask], distances[0][valid_mask], np.arange(len(labels[0]))[valid_mask]):
            hits.append((int(vector_id), float(distance), int(order)))

        if not hits:
            return []

        values_clause = ", ".join(["(?, ?, ?)"] * len(hits))
        params: list[object] = []
        for vector_id, distance, order in hits:
            params.extend([vector_id, distance, order])

        # Metadata parquet scan, then conversations parquet scan
        params.append(str(self.metadata_path))
        params.append(self.conversations_glob)

        filter_params: list[object] = []
        where_clause = self._where_from_filters(filters, filter_params, table_alias="c")
        params.extend(filter_params)

        sql = f"""
        WITH hits(vector_id, distance, faiss_order) AS (
          VALUES {values_clause}
        )
        SELECT
          m.conversation_id,
          c.project_id,
          c.title,
          c.created_at,
          c.updated_at,
          c.message_count,
          c.file_path,
          m.chunk_text,
          m.message_start_index,
          m.message_end_index,
          hits.distance,
          hits.faiss_order
        FROM hits
        JOIN parquet_scan(?) AS m
          ON m.vector_id = hits.vector_id
        JOIN (
          SELECT conversation_id, project_id, title, created_at,
                 updated_at, message_count, file_path
          FROM parquet_scan(?)
          QUALIFY row_number() OVER (
              PARTITION BY conversation_id ORDER BY updated_at DESC NULLS LAST
          ) = 1
        ) AS c
          ON c.conversation_id = m.conversation_id
        WHERE {where_clause}
        QUALIFY row_number() OVER (PARTITION BY m.conversation_id ORDER BY hits.faiss_order) = 1
        ORDER BY hits.faiss_order
        """
        rows = self._con.execute(sql, params).fetchall()

        if not rows:
            return []

        search_results = []
        for (
            conversation_id,
            project_id,
            title,
            created_at,
            updated_at,
            message_count,
            file_path,
            chunk_text,
            message_start_index,
            message_end_index,
            distance,
            _faiss_order,
        ) in rows:
            score = 1.0 / (1.0 + float(distance))
            snippet_text = chunk_text or ""
            snippet = snippet_text[:300] + ("..." if len(snippet_text) > 300 else "")

            search_results.append(
                SearchResult(
                    conversation_id=conversation_id,
                    project_id=project_id,
                    title=title,
                    created_at=created_at,
                    updated_at=updated_at,
                    message_count=message_count,
                    file_path=file_path,
                    score=score,
                    snippet=snippet,
                    message_start_index=int(message_start_index),
                    message_end_index=int(message_end_index),
                )
            )

        return search_results
    
    def _merge_results(
        self, 
        keyword: list[SearchResult], 
        semantic: list[SearchResult]
    ) -> list[SearchResult]:
        scores: dict[str, float] = defaultdict(float)
        result_map: dict[str, SearchResult] = {}
        
        # Normalize keyword scores
        if keyword:
            max_keyword_score = max(r.score for r in keyword) if keyword else 1.0
            min_keyword_score = min(r.score for r in keyword) if keyword else 0.0
            score_range = max_keyword_score - min_keyword_score if max_keyword_score != min_keyword_score else 1.0
            
            for rank, result in enumerate(keyword, 1):
                # Normalized score (0-1) with rank-based decay
                norm_score = (result.score - min_keyword_score) / score_range
                rank_weight = 1.0 / (1.0 + 0.1 * rank)  # Gentler decay than RRF
                weighted_score = norm_score * rank_weight * 0.6  # 60% weight for keyword
                
                scores[result.conversation_id] += weighted_score
                result_map[result.conversation_id] = result
        
        # Normalize semantic scores
        if semantic:
            max_semantic_score = max(r.score for r in semantic) if semantic else 1.0
            min_semantic_score = min(r.score for r in semantic) if semantic else 0.0
            score_range = max_semantic_score - min_semantic_score if max_semantic_score != min_semantic_score else 1.0
            
            for rank, result in enumerate(semantic, 1):
                # Normalized score (0-1) with rank-based decay
                norm_score = (result.score - min_semantic_score) / score_range
                rank_weight = 1.0 / (1.0 + 0.1 * rank)
                weighted_score = norm_score * rank_weight * 0.4  # 40% weight for semantic
                
                scores[result.conversation_id] += weighted_score
                if result.conversation_id not in result_map:
                    result_map[result.conversation_id] = result
        
        # Boost scores for results appearing in both
        keyword_ids = {r.conversation_id for r in keyword}
        semantic_ids = {r.conversation_id for r in semantic}
        for conv_id in scores:
            if conv_id in keyword_ids and conv_id in semantic_ids:
                scores[conv_id] *= 1.2  # 20% boost for appearing in both

        # Optional temporal decay: multiply by a recency-based factor.
        if getattr(self.config.search, "temporal_decay_enabled", False):
            import math
            from datetime import datetime, timezone

            factor = float(getattr(self.config.search, "temporal_decay_factor", 0.0))
            weight = float(getattr(self.config.search, "temporal_weight", 0.0))
            if factor < 0:
                raise ValueError("temporal_decay_factor must be >= 0")
            if weight < 0:
                raise ValueError("temporal_weight must be >= 0")

            now = datetime.now(timezone.utc)
            for conv_id in list(scores.keys()):
                r = result_map.get(conv_id)
                if r is None or r.updated_at is None:
                    continue
                updated = r.updated_at
                if updated.tzinfo is None:
                    updated = updated.replace(tzinfo=timezone.utc)
                age_days = max(0.0, (now - updated).total_seconds() / 86400.0)
                decay = math.exp(-factor * age_days)
                scores[conv_id] *= (1.0 + weight * decay)
        
        final_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        merged = []
        for conv_id, score in final_results[:50]:
            result = result_map[conv_id]
            result.score = score
            merged.append(result)
        
        return merged

    def _rerank(self, query: str, results: list[SearchResult]) -> list[SearchResult]:
        """Re-rank results using cross-encoder if enabled."""
        if not self.config.reranking.enabled or not results:
            return results

        if self._reranker is None:
            from sentence_transformers import CrossEncoder
            self._reranker = CrossEncoder(self.config.reranking.model)

        top_k = min(self.config.reranking.top_k, len(results))
        candidates = results[:top_k]
        remainder = results[top_k:]

        pairs = [(query, r.snippet) for r in candidates]
        scores = self._reranker.predict(pairs)

        for result, score in zip(candidates, scores):
            result.score = float(score)

        candidates.sort(key=lambda r: r.score, reverse=True)
        return candidates + remainder

    def _create_snippet(self, full_text: str, query: str, length: int = 200) -> str:
        """Create snippet using sliding-window term-density scoring."""
        parsed = self.query_parser.parse(query)
        terms = [t.lower() for t in parsed.exact_phrases + parsed.must_include + parsed.should_include]

        if not terms:
            return full_text[:length] + ("..." if len(full_text) > length else "")

        # Cap text to avoid O(n) scans on very long conversations
        capped_text = full_text[:50000]
        text_lower = capped_text.lower()

        best_score = -1
        best_start = 0

        step = max(1, length // 4)
        for start in range(0, max(1, len(capped_text) - length), step):
            window = text_lower[start:start + length]
            score = sum(window.count(term) for term in terms)
            if score > best_score:
                best_score = score
                best_start = start

        if best_score <= 0:
            return full_text[:length] + ("..." if len(full_text) > length else "")

        end = min(len(full_text), best_start + length)
        snippet = full_text[best_start:end]
        if best_start > 0:
            snippet = "..." + snippet
        if end < len(full_text):
            snippet = snippet + "..."
        return snippet
