"""Extraction pipeline — orchestrates heuristic and LLM extractors."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from searchat.config.settings import Config
from searchat.expertise.embeddings import ExpertiseEmbeddingIndex
from searchat.expertise.extractor import HeuristicExtractor
from searchat.expertise.models import ExpertiseRecord, RecordAction, RecordResult
from searchat.expertise.store import ExpertiseStore

logger = logging.getLogger(__name__)


@dataclass
class ExtractionStats:
    """Accumulates stats across a pipeline run."""

    conversations_processed: int = 0
    records_created: int = 0
    records_reinforced: int = 0
    records_flagged: int = 0
    heuristic_extracted: int = 0
    llm_extracted: int = 0
    errors: list[str] = field(default_factory=list)


class ExtractionPipeline:
    """Orchestrates extraction from conversation text into the expertise store.

    Supports three modes:
    - heuristic_only: fast regex pass (no LLM required)
    - full: heuristic + LLM extraction
    - llm_only: LLM extraction only
    """

    def __init__(
        self,
        store: ExpertiseStore,
        embedding_index: ExpertiseEmbeddingIndex | None,
        config: Config,
    ) -> None:
        self._store = store
        self._embedding_index = embedding_index
        self._config = config
        self._heuristic = HeuristicExtractor()

    def extract_from_text(
        self,
        text: str,
        *,
        domain: str = "general",
        project: str | None = None,
        conversation_id: str | None = None,
        mode: str = "heuristic_only",
    ) -> ExtractionStats:
        """Run extraction pipeline on a single text blob."""
        stats = ExtractionStats()
        records: list[ExpertiseRecord] = []

        if mode in ("heuristic_only", "full"):
            heuristic_records = self._heuristic.extract(text, domain=domain, project=project)
            for r in heuristic_records:
                if conversation_id:
                    object.__setattr__(r, "source_conversation_id", conversation_id)
            records.extend(heuristic_records)
            stats.heuristic_extracted += len(heuristic_records)

        if mode in ("llm_only", "full"):
            llm_records = self._run_llm_extraction(text, domain, project, conversation_id)
            records.extend(llm_records)
            stats.llm_extracted += len(llm_records)

        for record in records:
            result = self._store_with_dedup(record)
            if result.action == RecordAction.CREATED:
                stats.records_created += 1
            elif result.action == RecordAction.REINFORCED:
                stats.records_reinforced += 1
            elif result.action == RecordAction.DUPLICATE_FLAGGED:
                stats.records_flagged += 1

        stats.conversations_processed = 1
        return stats

    def extract_batch(
        self,
        conversations: list[dict[str, Any]],
        *,
        mode: str = "heuristic_only",
        default_domain: str = "general",
    ) -> ExtractionStats:
        """Run extraction on a batch of conversations.

        Each dict must have 'full_text' and optionally 'conversation_id', 'project_id'.
        """
        combined = ExtractionStats()
        for conv in conversations:
            text = conv.get("full_text", "")
            if not text or len(text.strip()) < 50:
                continue

            conv_id = conv.get("conversation_id")
            project = conv.get("project_id")
            domain = project or default_domain

            try:
                stats = self.extract_from_text(
                    text,
                    domain=domain,
                    project=project,
                    conversation_id=conv_id,
                    mode=mode,
                )
                combined.conversations_processed += stats.conversations_processed
                combined.records_created += stats.records_created
                combined.records_reinforced += stats.records_reinforced
                combined.records_flagged += stats.records_flagged
                combined.heuristic_extracted += stats.heuristic_extracted
                combined.llm_extracted += stats.llm_extracted
            except Exception as exc:
                msg = f"Extraction failed for conversation {conv_id}: {exc}"
                logger.warning(msg)
                combined.errors.append(msg)

        return combined

    def _run_llm_extraction(
        self,
        text: str,
        domain: str,
        project: str | None,
        conversation_id: str | None,
    ) -> list[ExpertiseRecord]:
        """Run LLM extraction, returning empty list on failure."""
        from searchat.expertise.llm_extractor import ExtractionError, LLMExtractor

        try:
            extractor = LLMExtractor(self._config.llm)
            records = extractor.extract(text, domain=domain, project=project)
            if conversation_id:
                for r in records:
                    object.__setattr__(r, "source_conversation_id", conversation_id)
            return records
        except ExtractionError as exc:
            logger.warning("LLM extraction failed: %s", exc)
            return []

    def _store_with_dedup(self, record: ExpertiseRecord) -> RecordResult:
        """Insert record with semantic dedup via embedding index."""
        if self._embedding_index is not None:
            similar = self._embedding_index.find_similar(record.content, limit=1)
            if similar:
                existing_id, score = similar[0]
                threshold = self._config.expertise.dedup_similarity_threshold
                flag_threshold = self._config.expertise.dedup_flag_threshold

                if score >= threshold:
                    # Reinforce existing record
                    self._store.validate_record(existing_id)
                    return RecordResult(
                        record=record,
                        action=RecordAction.REINFORCED,
                        existing_id=existing_id,
                    )
                if score >= flag_threshold:
                    return RecordResult(
                        record=record,
                        action=RecordAction.DUPLICATE_FLAGGED,
                        existing_id=existing_id,
                    )

        # New record — store and index
        self._store.insert(record)
        if self._embedding_index is not None:
            self._embedding_index.add(record)

        return RecordResult(record=record, action=RecordAction.CREATED)


def create_pipeline(config: Config, data_dir: Path) -> ExtractionPipeline:
    """Factory that wires up store, embeddings, and config."""
    store = ExpertiseStore(data_dir)
    embedding_index: ExpertiseEmbeddingIndex | None = None
    if config.expertise.enabled:
        embedding_index = ExpertiseEmbeddingIndex(
            data_dir,
            embedding_model=config.embedding.model,
        )
    return ExtractionPipeline(store, embedding_index, config)
