"""Fixture benchmark query set for M9's recall@10 and index-size-reduction
acceptance criteria (DEVELOPMENT_PLAN.md M9, Section D).

Builds a synthetic, deterministic 12-month conversation corpus with known
topic clusters and topic-matching queries, entirely with hand-constructed
384-dim vectors (no real embedding model, no real FAISS/ANN search): topic,
exchange, query, and distillate embeddings are all pure functions of a
topic name (+ deterministic noise modelling embedding drift), so recall is
measured against ground-truth semantic structure the test controls, not an
ML model's incidental output. Top-k retrieval is exact brute-force cosine
similarity -- mathematically identical to `faiss.IndexFlatL2` (itself an
exact, not approximate, index) for the corpus sizes used here.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np

EMBEDDING_DIM = 384

TOPICS: tuple[str, ...] = tuple(f"topic-{i:02d}" for i in range(12))


def _topic_vector(topic: str, *, noise: float, salt: str) -> list[float]:
    """Deterministic unit vector for `topic`, perturbed by Gaussian noise
    seeded from `salt` -- models embedding drift between two encodings of
    semantically-equivalent content (e.g. verbatim text vs. an LLM
    distillate of it) while keeping every vector reproducible run to run.
    """
    base_seed = int(hashlib.sha256(topic.encode()).hexdigest()[:8], 16)
    base = np.random.default_rng(base_seed).standard_normal(EMBEDDING_DIM)

    if noise:
        noise_seed = int(hashlib.sha256(f"{topic}:{salt}".encode()).hexdigest()[:8], 16)
        base = base + noise * np.random.default_rng(noise_seed).standard_normal(EMBEDDING_DIM)

    norm = np.linalg.norm(base)
    return (base / norm).astype(np.float32).tolist()


@dataclass(frozen=True)
class BenchmarkExchange:
    conversation_id: str
    exchange_id: str
    sequence_start: int
    sequence_end: int
    text: str
    verbatim_embedding: list[float]


@dataclass(frozen=True)
class BenchmarkConversation:
    conversation_id: str
    project_id: str
    topic: str
    month_index: int
    updated_at: datetime
    exchanges: list[BenchmarkExchange]


@dataclass(frozen=True)
class BenchmarkQuery:
    query_id: str
    topic: str
    query_embedding: list[float]
    relevant_conversation_ids: frozenset[str]


def build_fixture_corpus(
    *,
    months: int = 12,
    conversations_per_month: int = 2,
    exchanges_per_conversation: int = 5,
    base_date: datetime = datetime(2026, 7, 1),
    verbatim_noise: float = 0.05,
) -> list[BenchmarkConversation]:
    """A synthetic corpus spanning `months` months of history (one topic per
    month, oldest-first as `month_index` increases), `conversations_per_month`
    conversations per topic, each with `exchanges_per_conversation` exchanges
    clustered tightly around that month's topic vector.
    """
    conversations: list[BenchmarkConversation] = []
    for month_index in range(months):
        topic = TOPICS[month_index % len(TOPICS)]
        updated_at = base_date - timedelta(days=30 * month_index)
        for conv_index in range(conversations_per_month):
            conversation_id = f"conv-{month_index:02d}-{conv_index}"
            exchanges = []
            for exc_index in range(exchanges_per_conversation):
                exchange_id = f"{conversation_id}-exc-{exc_index}"
                embedding = _topic_vector(
                    topic, noise=verbatim_noise, salt=f"verbatim:{exchange_id}"
                )
                exchanges.append(BenchmarkExchange(
                    conversation_id=conversation_id,
                    exchange_id=exchange_id,
                    sequence_start=2 * exc_index,
                    sequence_end=2 * exc_index + 1,
                    text=f"[{topic}] exchange {exc_index} of {conversation_id}",
                    verbatim_embedding=embedding,
                ))
            conversations.append(BenchmarkConversation(
                conversation_id=conversation_id,
                project_id="benchmark",
                topic=topic,
                month_index=month_index,
                updated_at=updated_at,
                exchanges=exchanges,
            ))
    return conversations


def build_query_set(conversations: list[BenchmarkConversation]) -> list[BenchmarkQuery]:
    """One query per topic, embedded close to that topic's vector; ground
    truth = every conversation sharing that topic."""
    queries = []
    for topic in sorted({c.topic for c in conversations}):
        relevant = frozenset(c.conversation_id for c in conversations if c.topic == topic)
        queries.append(BenchmarkQuery(
            query_id=f"query-{topic}",
            topic=topic,
            query_embedding=_topic_vector(topic, noise=0.02, salt="query"),
            relevant_conversation_ids=relevant,
        ))
    return queries


def distillate_embedding(topic: str, conversation_id: str, *, noise: float = 0.15) -> list[float]:
    """Deterministic distillate embedding for `conversation_id` -- larger
    noise than `build_fixture_corpus`'s verbatim embeddings, modelling the
    extra drift an LLM-generated summary introduces relative to verbatim
    text of the same underlying exchange."""
    return _topic_vector(topic, noise=noise, salt=f"distillate:{conversation_id}")


def _cosine_topk(
    query_embedding: list[float], candidates: list[tuple[str, list[float]]], k: int
) -> list[str]:
    """Exact top-k by cosine similarity -- brute force, mathematically
    identical to `faiss.IndexFlatL2` (also exact) for these corpus sizes."""
    query = np.asarray(query_embedding, dtype=np.float32)
    query = query / np.linalg.norm(query)
    scored = []
    for item_id, vector in candidates:
        v = np.asarray(vector, dtype=np.float32)
        v = v / np.linalg.norm(v)
        scored.append((item_id, float(np.dot(query, v))))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [item_id for item_id, _ in scored[:k]]


def recall_at_k(
    queries: list[BenchmarkQuery],
    embedding_by_conversation: dict[str, list[float]],
    *,
    k: int = 10,
) -> float:
    """Mean recall@k across `queries` against a one-embedding-per-conversation
    candidate index (`embedding_by_conversation`): for each query, recall is
    `|top-k results intersect relevant| / min(k, |relevant|)`.
    """
    if not queries:
        return 0.0
    candidates = list(embedding_by_conversation.items())
    scores = []
    for query in queries:
        top = _cosine_topk(query.query_embedding, candidates, k)
        hits = sum(1 for conv_id in top if conv_id in query.relevant_conversation_ids)
        denom = min(k, len(query.relevant_conversation_ids))
        scores.append(hits / denom if denom else 0.0)
    return sum(scores) / len(scores)


# M9 acceptance budget (DEVELOPMENT_PLAN.md Section D, ASSUMPTION in the
# enhancement analysis Part 5 E3.1 / §2 Gap 3): distilled-conversation
# recall@10 must stay within 10% relative of pre-distillation verbatim
# recall, and index size must shrink at least 5x on a 12-month corpus.
MAX_RELATIVE_RECALL_DROP = 0.10
MIN_INDEX_SIZE_REDUCTION_FACTOR = 5.0
