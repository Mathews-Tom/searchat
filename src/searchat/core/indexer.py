from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path
from dataclasses import asdict

import numpy as np
import faiss
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from searchat.core.logging_config import get_logger
from searchat.core.progress import ProgressCallback, NullProgressAdapter
from searchat.models import (
    ConversationRecord,
    MessageRecord,
    IndexStats,
    UpdateStats,
    CONVERSATION_SCHEMA,
    METADATA_SCHEMA,
    FILE_STATE_SCHEMA,
    CODE_BLOCK_SCHEMA,
)
from searchat.config import Config, PathResolver
from searchat.config.constants import (
    INDEX_SCHEMA_VERSION,
    INDEX_FORMAT_VERSION,
    INDEX_FORMAT,
    INDEX_METADATA_FILENAME,
)
from searchat.core.connectors import discover_all_files, detect_connector

logger = get_logger(__name__)


def _build_id_selector(ids: np.ndarray) -> faiss.IDSelector:
    try:
        return faiss.IDSelectorBatch(ids)  # type: ignore[call-arg]
    except Exception:
        return faiss.IDSelectorBatch(ids.size, faiss.swig_ptr(ids))  # type: ignore[call-arg]


class ConversationIndexer:
    """
    Indexes conversations from multiple AI coding agents.

    Supported agents:
    - Claude Code: ~/.claude/projects/**/*.jsonl
    - Mistral Vibe: ~/.vibe/logs/session/*.json
    - OpenCode: ~/.local/share/opencode/storage/session/*/*.json
    """

    def __init__(self, search_dir: Path, config: Config | None = None):
        self.search_dir = search_dir
        self.data_dir = search_dir / "data"
        self.conversations_dir = self.data_dir / "conversations"
        self.indices_dir = self.data_dir / "indices"
        self.code_dir = self.data_dir / "code"
        self.indexed_paths_path = self.indices_dir / "indexed_paths.parquet"
        self.file_state_path = self.indices_dir / "file_state.parquet"

        if config is None:
            config = Config.load()
        self.config = config

        # Embedder is initialized lazily (first indexing operation).
        self._embedder = None

        self.batch_size = config.embedding.batch_size
        self.chunk_size = 1500
        self.chunk_overlap = 200

        self._ensure_directories()

    def _write_indexed_paths(self, paths: set[str]) -> None:
        """Persist the set of indexed source file paths.

        This avoids scanning all conversation parquets on every watcher start.
        """
        table = pa.Table.from_pydict({"file_path": sorted(paths)})
        pq.write_table(table, self.indexed_paths_path)

    def _load_file_state(self) -> dict[str, dict]:
        if not self.file_state_path.exists():
            return {}
        table = pq.read_table(self.file_state_path)
        state: dict[str, dict] = {}
        for row in table.to_pylist():
            file_path = row.get("file_path")
            if isinstance(file_path, str):
                state[file_path] = row
        return state

    def _write_file_state(self, entries: list[dict]) -> None:
        table = pa.Table.from_pylist(entries, schema=FILE_STATE_SCHEMA)
        pq.write_table(table, self.file_state_path)

    def _backfill_file_state(self) -> dict[str, dict]:
        state: dict[str, dict] = {}
        for parquet_file in self.conversations_dir.glob("*.parquet"):
            table = pq.read_table(
                parquet_file,
                columns=["file_path", "file_hash", "indexed_at", "conversation_id", "project_id"],
            )
            for row in table.to_pylist():
                file_path = row.get("file_path")
                if not isinstance(file_path, str):
                    continue
                file_size = 0
                path_obj = Path(file_path)
                if path_obj.exists():
                    file_size = path_obj.stat().st_size
                connector_name = "unknown"
                try:
                    connector_name = detect_connector(path_obj).name
                except Exception:
                    connector_name = "unknown"
                state[file_path] = {
                    "file_path": file_path,
                    "file_hash": row.get("file_hash"),
                    "file_size": file_size,
                    "indexed_at": row.get("indexed_at"),
                    "connector_name": connector_name,
                    "conversation_id": row.get("conversation_id"),
                    "project_id": row.get("project_id"),
                }
        return state

    def _get_embedder(self):
        """Create and cache the embedding model on first use."""
        if self._embedder is not None:
            return self._embedder

        # Check for GPU availability and warn if not using it
        from searchat.gpu_check import check_and_warn_gpu

        check_and_warn_gpu()

        from sentence_transformers import SentenceTransformer

        device = self.config.embedding.get_device()
        logger.info(f"Initializing embedding model on device: {device}")
        self._embedder = SentenceTransformer(self.config.embedding.model, device=device)
        return self._embedder
    
    def _ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.conversations_dir.mkdir(exist_ok=True)
        self.indices_dir.mkdir(exist_ok=True)
        self.code_dir.mkdir(exist_ok=True)
    
    def _chunk_text(self, text: str, chunk_size: int | None = None, overlap: int | None = None) -> list[str]:
        if chunk_size is None:
            chunk_size = self.chunk_size
        if overlap is None:
            overlap = self.chunk_overlap
        
        if len(text) <= chunk_size:
            return [text]

        # Fast path for long unstructured text (no sentence boundaries): fixed-size chunks.
        if not re.search(r"[.!?]", text):
            overlap = max(0, min(overlap, chunk_size - 1))
            chunks: list[str] = []
            start = 0
            while start < len(text):
                end = min(start + chunk_size, len(text))
                chunks.append(text[start:end])
                if end >= len(text):
                    break
                start = max(0, end - overlap)
            return chunks
        
        # Split by sentences (simple approach using common punctuation)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        chunks = []
        current_chunk = []
        current_size = 0
        
        for sentence in sentences:
            sentence_size = len(sentence)
            
            # If single sentence exceeds chunk size, split it
            if sentence_size > chunk_size:
                # Add current chunk if it exists
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                    current_chunk = []
                    current_size = 0
                
                # Split long sentence by words
                words = sentence.split()
                temp_chunk = []
                temp_size = 0
                
                for word in words:
                    word_size = len(word) + 1  # +1 for space
                    if temp_size + word_size > chunk_size and temp_chunk:
                        chunks.append(' '.join(temp_chunk))
                        temp_chunk = [word]
                        temp_size = word_size
                    else:
                        temp_chunk.append(word)
                        temp_size += word_size
                
                if temp_chunk:
                    chunks.append(' '.join(temp_chunk))
            
            # If adding sentence exceeds chunk size, start new chunk
            elif current_size + sentence_size + 1 > chunk_size and current_chunk:
                chunks.append(' '.join(current_chunk))
                # Keep last sentences for overlap
                overlap_text = ' '.join(current_chunk[-2:]) if len(current_chunk) > 1 else ''
                current_chunk = [overlap_text, sentence] if overlap_text and overlap > 0 else [sentence]
                current_size = len(overlap_text) + sentence_size + 1 if overlap_text else sentence_size
            else:
                current_chunk.append(sentence)
                current_size += sentence_size + 1
        
        # Add remaining chunk
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks
    
    def _chunk_by_messages(self, messages: list[MessageRecord], title: str) -> list[dict]:
        chunks_with_metadata = []
        current_chunk = f"{title}\n\n"
        current_messages = []
        start_message_idx = 0
        
        for idx, msg in enumerate(messages):
            msg_text = f"{msg.content}\n\n"
            
            if len(current_chunk) + len(msg_text) > self.chunk_size and current_messages:
                chunks_with_metadata.append({
                    'text': current_chunk,
                    'start_message_index': start_message_idx,
                    'end_message_index': current_messages[-1]
                })
                
                overlap_size = 0
                overlap_messages = []
                for msg_idx in reversed(current_messages):
                    overlap_msg = messages[msg_idx]
                    overlap_text = f"{overlap_msg.role}: {overlap_msg.content}\n\n"
                    if overlap_size + len(overlap_text) <= self.chunk_overlap:
                        overlap_messages.insert(0, msg_idx)
                        overlap_size += len(overlap_text)
                    else:
                        break
                
                if overlap_messages:
                    current_chunk = ""
                    for msg_idx in overlap_messages:
                        overlap_msg = messages[msg_idx]
                        current_chunk += f"{overlap_msg.role}: {overlap_msg.content}\n\n"
                    start_message_idx = overlap_messages[0]
                    current_messages = overlap_messages.copy()
                else:
                    current_chunk = ""
                    current_messages = []
                    start_message_idx = idx
            
            current_chunk += msg_text
            current_messages.append(idx)
        
        if current_chunk.strip():
            chunks_with_metadata.append({
                'text': current_chunk,
                'start_message_index': start_message_idx,
                'end_message_index': current_messages[-1] if current_messages else 0
            })
        
        return chunks_with_metadata
    
    def index_all(
        self,
        force: bool = False,
        progress: ProgressCallback | None = None,
    ) -> IndexStats:
        """
        Build index from scratch by scanning all supported source files.

        SAFETY: If an existing index is detected, this requires force=True
        to prevent accidental data loss. The existing index will be completely
        replaced with data from current source files.

        Args:
            force: Must be True to rebuild when existing index is present.
                   This acknowledges that existing indexed data will be lost
                   if source JSONLs are missing or incomplete.
            progress: Optional progress callback for reporting

        Returns:
            IndexStats with indexing results

        Raises:
            RuntimeError: If existing index found and force=False
        """
        if progress is None:
            progress = NullProgressAdapter()
        if not self.config.indexing.enable_connectors:
            raise RuntimeError(
                "Connector loading is disabled. Set indexing.enable_connectors to true."
            )
        has_existing_index = self._has_existing_index()

        if has_existing_index and not force:
            raise RuntimeError(
                "Existing index detected. Full rebuild will REPLACE all indexed data.\n\n"
                "If source JSONLs are missing or incomplete, you will lose conversations.\n\n"
                "Options:\n"
                "  1. Use index_append_only() to safely add new conversations\n"
                "  2. Call index_all(force=True) if you have complete source files\n"
                "  3. Delete index manually: rm -rf <search_dir>/data/\n\n"
                f"Index location: {self.data_dir}"
            )

        if has_existing_index:
            logger.warning(
                f"Force rebuilding index. Existing data at {self.data_dir} will be replaced."
            )
            # Clear existing data
            import shutil
            if self.conversations_dir.exists():
                shutil.rmtree(self.conversations_dir)
            if self.indices_dir.exists():
                shutil.rmtree(self.indices_dir)
            self._ensure_directories()

        start_time = time.time()

        # Phase 1: Discovery
        progress.update_phase("Discovering conversation files")

        # Collect all files first for accurate progress tracking
        file_matches = discover_all_files(self.config)

        # Phase 2: Processing conversations
        progress.update_phase("Processing conversations")

        all_records: list[ConversationRecord] = []
        all_chunks_with_meta: list[dict] = []
        project_records_map: dict[str, list[ConversationRecord]] = {}
        file_state_entries: list[dict] = []
        connector_name_by_file_path: dict[str, str] = {}

        for idx, match in enumerate(file_matches, 1):
            json_file = match.path
            connector = match.connector
            display_name = f"{connector.name} | {json_file.name}"
            progress.update_file_progress(idx, len(file_matches), display_name)

            try:
                # Process based on agent type
                record = connector.parse(json_file, 0)

                # Skip conversations with no messages
                if record.message_count == 0:
                    continue

                all_records.append(record)

                connector_name_by_file_path[record.file_path] = connector.name

                project_key = record.project_id
                if project_key not in project_records_map:
                    project_records_map[project_key] = []
                project_records_map[project_key].append(record)

                file_size = json_file.stat().st_size if json_file.exists() else 0
                file_state_entries.append({
                    "file_path": record.file_path,
                    "file_hash": record.file_hash,
                    "file_size": file_size,
                    "indexed_at": record.indexed_at,
                    "connector_name": connector.name,
                    "conversation_id": record.conversation_id,
                    "project_id": record.project_id,
                })

                # Collect chunks (will batch encode later)
                chunks_with_meta = self._chunk_by_messages(record.messages, record.title)
                for chunk_idx, chunk in enumerate(chunks_with_meta):
                    chunk["_record"] = record
                    chunk["_chunk_index"] = chunk_idx
                    all_chunks_with_meta.append(chunk)

            except Exception as e:
                if connector.name == "claude":
                    raise RuntimeError(f"Failed to process {json_file}: {e}") from e
                logger.warning(f"Failed to process {connector.name} session {json_file}: {e}")
                continue

        # Phase 3: Generate embeddings
        progress.update_phase("Generating embeddings")
        embeddings_array = self._batch_encode_chunks(all_chunks_with_meta, progress)

        # Build metadata for FAISS index
        metadata: list[dict] = []
        vector_ids: list[int] = []
        next_vector_id = 0
        record_first_vector_id: dict[str, int] = {}
        for chunk_meta, _embedding in zip(all_chunks_with_meta, embeddings_array):
            record = chunk_meta["_record"]
            if record.conversation_id not in record_first_vector_id:
                record_first_vector_id[record.conversation_id] = next_vector_id
            vector_id = next_vector_id
            next_vector_id += 1
            vector_ids.append(vector_id)
            metadata.append({
                "vector_id": vector_id,
                "conversation_id": record.conversation_id,
                "project_id": record.project_id,
                "chunk_index": chunk_meta["_chunk_index"],
                "chunk_text": chunk_meta["text"],
                "message_start_index": chunk_meta["start_message_index"],
                "message_end_index": chunk_meta["end_message_index"],
                "created_at": record.created_at,
            })

        # Phase 4: Building index
        progress.update_phase("Building search index")
        if len(embeddings_array) > 0:
            self._build_faiss_index(embeddings_array, metadata, vector_ids)

        # Phase 5: Saving
        progress.update_phase("Writing to storage")
        for project_id, records in project_records_map.items():
            for record in records:
                record.embedding_id = record_first_vector_id.get(record.conversation_id, 0)
            self._write_parquet_batch(records, project_id, connector_name_by_file_path)

        self._write_index_metadata(
            len(all_records),
            len(embeddings_array),
            next_vector_id=next_vector_id,
        )

        # Persist indexed source paths for fast watcher startup.
        self._write_indexed_paths({r.file_path for r in all_records})
        if file_state_entries:
            self._write_file_state(file_state_entries)

        # Update final stats
        progress.update_stats(
            conversations=len(all_records),
            chunks=len(all_chunks_with_meta),
            embeddings=len(embeddings_array)
        )
        progress.finish()

        elapsed = time.time() - start_time
        
        parquet_size = sum(
            f.stat().st_size for f in self.conversations_dir.glob("*.parquet")
        ) / (1024 * 1024)
        
        faiss_path = self.indices_dir / "embeddings.faiss"
        faiss_size = faiss_path.stat().st_size / (1024 * 1024) if faiss_path.exists() else 0
        
        return IndexStats(
            total_conversations=len(all_records),
            total_messages=sum(r.message_count for r in all_records),
            index_time_seconds=elapsed,
            parquet_size_mb=parquet_size,
            faiss_size_mb=faiss_size
        )

    def _batch_encode_chunks(
        self,
        chunks_with_meta: list[dict],
        progress: ProgressCallback | None = None,
    ) -> np.ndarray:
        """
        Encode chunks in batches for better performance.
        Uses configured batch_size to avoid memory issues.

        Args:
            chunks_with_meta: List of chunks with metadata
            progress: Optional progress callback

        Returns:
            Embeddings array
        """
        if progress is None:
            progress = NullProgressAdapter()

        if not chunks_with_meta:
            return np.array([])

        texts = [chunk['text'] for chunk in chunks_with_meta]

        # Encode in batches manually to report progress
        all_embeddings = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            embedder = self._get_embedder()
            batch_embeddings = embedder.encode(
                batch,
                batch_size=self.batch_size,
                show_progress_bar=False,
                convert_to_numpy=True
            )
            all_embeddings.extend(batch_embeddings)

            # Update progress
            progress.update_embedding_progress(
                current=min(i + self.batch_size, len(texts)),
                total=len(texts)
            )

        return np.array(all_embeddings)

    def _process_conversation(self, json_path: Path, project_id: str, embedding_id: int) -> ConversationRecord:
        with open(json_path, 'r', encoding='utf-8') as f:
            lines = [json.loads(line) for line in f]
        
        file_hash = hashlib.sha256(json_path.read_bytes()).hexdigest()
        
        conversation_id = json_path.stem
        def _extract_content(entry):
            raw = entry.get('message', {})
            raw_content = raw.get('content', raw.get('text', ''))
            if isinstance(raw_content, str):
                return raw_content
            if isinstance(raw_content, list):
                return '\n\n'.join(
                    block.get('text', '')
                    for block in raw_content
                    if block.get('type') == 'text'
                )
            return ''

        title = 'Untitled'
        for entry in lines:
            text = _extract_content(entry).strip()
            if text:
                title = text[:100]
                break
        
        messages: list[MessageRecord] = []
        full_text_parts: list[str] = []
        
        for idx, entry in enumerate(lines):
            msg_type = entry.get('type')
            if msg_type not in ('user', 'assistant'):
                continue
            
            role = msg_type
            content = _extract_content(entry)
            
            code_blocks = re.findall(r'```(?:\w+)?\n(.*?)```', content, re.DOTALL)
            has_code = len(code_blocks) > 0
            
            timestamp_str = entry.get('timestamp')
            timestamp = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now()
            
            messages.append(MessageRecord(
                sequence=len(messages),
                role=role,
                content=content,
                timestamp=timestamp,
                has_code=has_code,
                code_blocks=code_blocks
            ))
            
            full_text_parts.append(content)
        
        full_text = "\n\n".join(full_text_parts)
        
        created_at = messages[0].timestamp if messages else datetime.now()
        updated_at = messages[-1].timestamp if messages else datetime.now()
        
        return ConversationRecord(
            conversation_id=conversation_id,
            project_id=project_id,
            file_path=str(json_path),
            title=title,
            created_at=created_at,
            updated_at=updated_at,
            message_count=len(messages),
            messages=messages,
            full_text=full_text,
            embedding_id=embedding_id,
            file_hash=file_hash,
            indexed_at=datetime.now()
        )

    def _detect_agent_format(self, file_path: Path) -> str:
        """
        Detect which AI agent format a file belongs to.

        Args:
            file_path: Path to conversation file

        Returns:
            'claude' for Claude Code JSONL, 'vibe' for Mistral Vibe JSON
        """
        # Check by extension first
        if file_path.suffix == '.jsonl':
            return 'claude'
        elif file_path.suffix == '.json':
            if "storage" in file_path.parts and "session" in file_path.parts:
                return 'opencode'
            # Check if it's in a Vibe directory
            if '.vibe' in str(file_path):
                return 'vibe'
            # Check file structure
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if 'projectID' in data and 'sessionID' in data:
                    return 'opencode'
                if 'metadata' in data and 'messages' in data:
                    return 'vibe'
            except (json.JSONDecodeError, KeyError):
                pass
        return 'unknown'

    def _process_vibe_session(self, json_path: Path, embedding_id: int) -> ConversationRecord:
        """
        Process a Mistral Vibe session JSON file.

        Args:
            json_path: Path to Vibe session JSON
            embedding_id: Embedding ID for this conversation

        Returns:
            ConversationRecord with parsed session data
        """
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        file_hash = hashlib.sha256(json_path.read_bytes()).hexdigest()

        metadata = data.get('metadata', {})
        session_id = metadata.get('session_id', json_path.stem)

        # Extract project from working directory
        env = metadata.get('environment', {})
        working_dir = env.get('working_directory', '')
        project_id = Path(working_dir).name if working_dir else 'vibe-session'

        # Parse timestamps
        start_time_str = metadata.get('start_time')
        end_time_str = metadata.get('end_time')
        created_at = datetime.fromisoformat(start_time_str) if start_time_str else datetime.now()
        updated_at = datetime.fromisoformat(end_time_str) if end_time_str else created_at

        # Parse messages
        messages: list[MessageRecord] = []
        full_text_parts: list[str] = []
        title = 'Untitled Vibe Session'

        for msg in data.get('messages', []):
            role = msg.get('role')

            # Skip system messages and tool responses for search
            if role not in ('user', 'assistant'):
                continue

            content = msg.get('content', '')

            # Skip empty content (tool_calls without text)
            if not content:
                continue

            # Extract title from first user message
            if role == 'user' and title == 'Untitled Vibe Session':
                title = content[:100].replace('\n', ' ').strip()

            code_blocks = re.findall(r'```(?:\w+)?\n(.*?)```', content, re.DOTALL)
            has_code = len(code_blocks) > 0

            messages.append(MessageRecord(
                sequence=len(messages),
                role=role,
                content=content,
                timestamp=created_at,  # Vibe doesn't have per-message timestamps
                has_code=has_code,
                code_blocks=code_blocks
            ))

            full_text_parts.append(content)

        full_text = "\n\n".join(full_text_parts)

        return ConversationRecord(
            conversation_id=session_id,
            project_id=f"vibe-{project_id}",  # Prefix to distinguish from Claude projects
            file_path=str(json_path),
            title=title,
            created_at=created_at,
            updated_at=updated_at,
            message_count=len(messages),
            messages=messages,
            full_text=full_text,
            embedding_id=embedding_id,
            file_hash=file_hash,
            indexed_at=datetime.now()
        )

    def _process_any_conversation(self, file_path: Path, project_id: str, embedding_id: int) -> ConversationRecord:
        """
        Process a conversation file, auto-detecting the format.

        Args:
            file_path: Path to conversation file
            project_id: Project identifier
            embedding_id: Embedding ID

        Returns:
            ConversationRecord
        """
        agent_format = self._detect_agent_format(file_path)

        if agent_format == 'vibe':
            return self._process_vibe_session(file_path, embedding_id)
        elif agent_format == 'claude':
            return self._process_conversation(file_path, project_id, embedding_id)
        elif agent_format == 'opencode':
            return self._process_opencode_session(file_path, embedding_id)
        else:
            raise ValueError(f"Unknown conversation format: {file_path}")

    def _process_opencode_session(self, session_path: Path, embedding_id: int) -> ConversationRecord:
        """
        Process an OpenCode session JSON file.

        Args:
            session_path: Path to OpenCode session JSON
            embedding_id: Embedding ID for this conversation

        Returns:
            ConversationRecord with parsed session data
        """
        with open(session_path, 'r', encoding='utf-8') as f:
            session = json.load(f)

        file_hash = hashlib.sha256(session_path.read_bytes()).hexdigest()

        session_id = session.get("id") or session.get("sessionID") or session_path.stem
        project_id = session.get("projectID", "unknown")
        title = session.get("title") or "Untitled OpenCode Session"

        time_info = session.get("time", {})
        created_at = self._timestamp_ms_to_datetime(time_info.get("created"))
        updated_at = self._timestamp_ms_to_datetime(time_info.get("updated")) or created_at

        data_root = self._resolve_opencode_data_root(session_path)
        messages = self._load_opencode_messages(data_root, session_id)
        if not messages:
            for alt_root in PathResolver.resolve_opencode_dirs(self.config):
                if alt_root == data_root:
                    continue
                messages = self._load_opencode_messages(alt_root, session_id)
                if messages:
                    break
        if not messages:
            messages = self._load_opencode_session_messages(session, data_root)

        if title == "Untitled OpenCode Session":
            for msg in messages:
                if msg.content:
                    title = msg.content[:100].replace("\n", " ").strip()
                    break

        full_text_parts = [msg.content for msg in messages if msg.content]
        full_text = "\n\n".join(full_text_parts)

        return ConversationRecord(
            conversation_id=session_id,
            project_id=f"opencode-{project_id}",
            file_path=str(session_path),
            title=title,
            created_at=created_at or datetime.now(),
            updated_at=updated_at or datetime.now(),
            message_count=len(messages),
            messages=messages,
            full_text=full_text,
            embedding_id=embedding_id,
            file_hash=file_hash,
            indexed_at=datetime.now()
        )

    def _load_opencode_messages(self, data_root: Path, session_id: str) -> list[MessageRecord]:
        messages_dir = data_root / "storage" / "message" / session_id
        if not messages_dir.exists():
            return []

        raw_messages = []
        for message_file in messages_dir.glob("*.json"):
            try:
                with open(message_file, 'r', encoding='utf-8') as f:
                    message = json.load(f)
            except json.JSONDecodeError:
                continue

            role = message.get("role")
            if role not in ("user", "assistant"):
                continue

            content = self._extract_opencode_message_text(data_root, message)
            if not content:
                continue

            created_at = self._timestamp_ms_to_datetime(message.get("time", {}).get("created"))
            raw_messages.append((created_at, message_file.name, role, content))

        raw_messages.sort(key=lambda item: (item[0] or datetime.min, item[1]))

        messages: list[MessageRecord] = []
        for sequence, (created_at, _name, role, content) in enumerate(raw_messages):
            code_blocks = re.findall(r'```(?:\w+)?\n(.*?)```', content, re.DOTALL)
            has_code = len(code_blocks) > 0
            messages.append(MessageRecord(
                sequence=sequence,
                role=role,
                content=content,
                timestamp=created_at or datetime.now(),
                has_code=has_code,
                code_blocks=code_blocks
            ))

        return messages

    def _load_opencode_session_messages(self, session: dict, data_root: Path) -> list[MessageRecord]:
        session_messages = session.get("messages")
        if not isinstance(session_messages, list):
            return []

        raw_messages = []
        for index, entry in enumerate(session_messages):
            if not isinstance(entry, dict):
                continue
            role = entry.get("role") or entry.get("type")
            if role not in ("user", "assistant"):
                continue
            content = self._extract_opencode_message_text(data_root, entry)
            if not content:
                continue
            created_at = self._timestamp_ms_to_datetime(entry.get("time", {}).get("created"))
            raw_messages.append((created_at, f"{index:06d}", role, content))

        raw_messages.sort(key=lambda item: (item[0] or datetime.min, item[1]))

        messages: list[MessageRecord] = []
        for sequence, (created_at, _name, role, content) in enumerate(raw_messages):
            code_blocks = re.findall(r'```(?:\w+)?\n(.*?)```', content, re.DOTALL)
            has_code = len(code_blocks) > 0
            messages.append(MessageRecord(
                sequence=sequence,
                role=role,
                content=content,
                timestamp=created_at or datetime.now(),
                has_code=has_code,
                code_blocks=code_blocks
            ))

        return messages

    def _extract_opencode_message_text(self, data_root: Path, message: dict) -> str:
        def _normalize_text(value: object) -> str:
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, dict):
                text = value.get("text") or value.get("content") or value.get("value")
                if isinstance(text, str) and text.strip():
                    return text.strip()
            if isinstance(value, list):
                parts = []
                for block in value:
                    if not isinstance(block, dict):
                        continue
                    text = block.get("text") or block.get("content") or block.get("value")
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
                if parts:
                    return "\n\n".join(parts)
            return ""

        content_text = _normalize_text(message.get("content"))
        if content_text:
            return content_text

        text_text = _normalize_text(message.get("text"))
        if text_text:
            return text_text

        message_text = _normalize_text(message.get("message"))
        if message_text:
            return message_text

        message_id = message.get("id")
        if isinstance(message_id, str):
            parts_text = self._load_opencode_parts_text(data_root, message_id)
            if parts_text:
                return parts_text

        summary = message.get("summary")
        if isinstance(summary, dict):
            body = summary.get("body")
            if isinstance(body, str) and body.strip():
                return body.strip()

            title = summary.get("title")
            if isinstance(title, str) and title.strip():
                return title.strip()

        return ""

    def _load_opencode_parts_text(self, data_root: Path, message_id: str) -> str:
        parts_dir = data_root / "storage" / "part" / message_id
        if not parts_dir.exists():
            return ""

        parts = []
        for part_file in sorted(parts_dir.glob("*.json")):
            try:
                with open(part_file, 'r', encoding='utf-8') as f:
                    part = json.load(f)
            except json.JSONDecodeError:
                continue

            text = part.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
                continue

            state = part.get("state")
            if isinstance(state, dict):
                output = state.get("output")
                if isinstance(output, str) and output.strip():
                    parts.append(output.strip())

        return "\n\n".join(parts)

    def _resolve_opencode_data_root(self, session_path: Path) -> Path:
        if "storage" in session_path.parts:
            storage_index = session_path.parts.index("storage")
            return Path(*session_path.parts[:storage_index])
        if len(session_path.parents) >= 4:
            return session_path.parents[3]
        return session_path.parent

    @staticmethod
    def _timestamp_ms_to_datetime(value: int | None) -> datetime | None:
        if value is None:
            return None
        try:
            return datetime.fromtimestamp(value / 1000)
        except (OSError, ValueError, TypeError):
            return None

    def _write_parquet_batch(
        self,
        records: list[ConversationRecord],
        project_id: str,
        connector_name_by_file_path: dict[str, str],
    ) -> None:
        output_path = self.conversations_dir / f"project_{project_id}.parquet"
        
        data = {
            'conversation_id': [r.conversation_id for r in records],
            'project_id': [r.project_id for r in records],
            'file_path': [r.file_path for r in records],
            'title': [r.title for r in records],
            'created_at': [r.created_at for r in records],
            'updated_at': [r.updated_at for r in records],
            'message_count': [r.message_count for r in records],
            'messages': [
                [
                    asdict(m)
                    for m in r.messages
                ]
                for r in records
            ],
            'full_text': [r.full_text for r in records],
            'embedding_id': [r.embedding_id for r in records],
            'file_hash': [r.file_hash for r in records],
            'indexed_at': [r.indexed_at for r in records]
        }
        
        table = pa.Table.from_pydict(data, schema=CONVERSATION_SCHEMA)
        pq.write_table(table, output_path)

        code_rows: list[dict] = []
        for record in records:
            connector_name = connector_name_by_file_path.get(record.file_path)
            if not connector_name:
                raise RuntimeError(f"Missing connector name for indexed file: {record.file_path}")
            code_rows.extend(self._extract_code_block_dicts(record, connector_name))
        self._write_code_blocks(project_id, code_rows)

    def _record_to_dict(self, record: ConversationRecord) -> dict:
        return {
            "conversation_id": record.conversation_id,
            "project_id": record.project_id,
            "file_path": record.file_path,
            "title": record.title,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "message_count": record.message_count,
            "messages": [
                {
                    "sequence": m.sequence,
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp,
                    "has_code": m.has_code,
                    "code_blocks": m.code_blocks,
                }
                for m in record.messages
            ],
            "full_text": record.full_text,
            "embedding_id": record.embedding_id,
            "file_hash": record.file_hash,
            "indexed_at": record.indexed_at,
        }

    def _write_project_parquet_dicts(self, project_id: str, record_dicts: list[dict]) -> None:
        output_path = self.conversations_dir / f"project_{project_id}.parquet"
        table = pa.Table.from_pylist(record_dicts, schema=CONVERSATION_SCHEMA)
        pq.write_table(table, output_path)

    def _append_record_dicts(self, project_id: str, record_dicts: list[dict]) -> None:
        if not record_dicts:
            return
        project_parquet = self.conversations_dir / f"project_{project_id}.parquet"
        new_table = pa.Table.from_pylist(record_dicts, schema=CONVERSATION_SCHEMA)
        if project_parquet.exists():
            existing_table = pq.read_table(project_parquet)
            combined_table = pa.concat_tables([existing_table, new_table])
            pq.write_table(combined_table, project_parquet)
        else:
            pq.write_table(new_table, project_parquet)

    def _code_parquet_path(self, project_id: str) -> Path:
        return self.code_dir / f"project_{project_id}.parquet"

    def _write_code_blocks(self, project_id: str, code_rows: list[dict]) -> None:
        path = self._code_parquet_path(project_id)
        table = pa.Table.from_pylist(code_rows, schema=CODE_BLOCK_SCHEMA)
        pq.write_table(table, path)

    def _append_code_blocks(self, project_id: str, code_rows: list[dict]) -> None:
        if not code_rows:
            return
        path = self._code_parquet_path(project_id)
        new_table = pa.Table.from_pylist(code_rows, schema=CODE_BLOCK_SCHEMA)
        if path.exists():
            existing_table = pq.read_table(path)
            combined_table = pa.concat_tables([existing_table, new_table])
            pq.write_table(combined_table, path)
        else:
            pq.write_table(new_table, path)

    def _remove_code_blocks_for_conversation(self, project_id: str, conversation_id: str) -> None:
        path = self._code_parquet_path(project_id)
        if not path.exists():
            return
        table = pq.read_table(path)
        filtered = table.filter(pc.field("conversation_id") != conversation_id)
        pq.write_table(filtered, path)

    def _extract_code_block_dicts(self, record: ConversationRecord, connector_name: str) -> list[dict]:
        from searchat.core.code_extractor import extract_code_blocks

        rows: list[dict] = []
        for message in record.messages:
            extracted = extract_code_blocks(
                message_text=message.content,
                message_index=message.sequence,
                role=message.role,
            )
            for block in extracted:
                rows.append(
                    {
                        "conversation_id": record.conversation_id,
                        "project_id": record.project_id,
                        "connector": connector_name,
                        "file_path": record.file_path,
                        "title": record.title,
                        "conversation_created_at": record.created_at,
                        "conversation_updated_at": record.updated_at,
                        "message_index": block.message_index,
                        "block_index": block.block_index,
                        "role": block.role,
                        "message_timestamp": message.timestamp,
                        "fence_language": block.fence_language,
                        "language": block.language,
                        "language_source": block.language_source,
                        "functions": block.functions,
                        "classes": block.classes,
                        "imports": block.imports,
                        "code": block.code,
                        "code_hash": block.code_hash,
                        "lines": block.lines,
                    }
                )
        return rows

    def _remove_conversation_from_project(self, project_id: str, conversation_id: str) -> None:
        project_parquet = self.conversations_dir / f"project_{project_id}.parquet"
        if not project_parquet.exists():
            return
        table = pq.read_table(project_parquet)
        filtered = table.filter(pc.field("conversation_id") != conversation_id)
        pq.write_table(filtered, project_parquet)

    def _rebuild_idmap_index(
        self,
        existing_index: faiss.Index,
        remaining_ids: list[int],
        new_embeddings: list[np.ndarray],
        new_ids: list[int],
    ) -> faiss.Index:
        dimension = existing_index.d
        base_index = faiss.IndexFlatL2(dimension)  # type: ignore[call-arg]
        rebuilt_index = faiss.IndexIDMap2(base_index)  # type: ignore[call-arg]

        vectors: list[np.ndarray] = []
        ids: list[int] = []

        for vector_id in remaining_ids:
            try:
                vector = existing_index.reconstruct(int(vector_id))  # type: ignore[call-arg]
            except Exception as exc:
                raise RuntimeError(
                    "Failed to reconstruct existing vectors for rebuild."
                ) from exc
            vectors.append(vector)
            ids.append(int(vector_id))

        if new_embeddings:
            vectors.extend(new_embeddings)
            ids.extend(int(vector_id) for vector_id in new_ids)

        if vectors:
            vectors_array = np.vstack(vectors).astype(np.float32)
            ids_array = np.asarray(ids, dtype=np.int64)
            rebuilt_index.add_with_ids(vectors_array, ids_array)  # type: ignore[call-arg]

        return rebuilt_index
    
    def _build_faiss_index(
        self,
        embeddings: np.ndarray,
        metadata: list[dict],
        vector_ids: list[int],
    ) -> None:
        dimension = embeddings.shape[1]  # type: ignore[call-arg]
        n_vectors = embeddings.shape[0]  # type: ignore[call-arg]

        if n_vectors < 100:
            base_index = faiss.IndexFlatL2(dimension)  # type: ignore[call-arg]
        else:
            quantizer = faiss.IndexFlatL2(dimension)  # type: ignore[call-arg]
            base_index = faiss.IndexIVFFlat(quantizer, dimension, min(100, n_vectors // 10))  # type: ignore[call-arg]
            base_index.train(embeddings)  # type: ignore[call-arg,arg-type]

        index = faiss.IndexIDMap2(base_index)  # type: ignore[call-arg]
        id_array = np.asarray(vector_ids, dtype=np.int64)
        index.add_with_ids(embeddings, id_array)  # type: ignore[call-arg,arg-type]

        faiss.write_index(index, str(self.indices_dir / "embeddings.faiss"))  # type: ignore[call-arg]

        metadata_table = pa.Table.from_pylist(metadata, schema=METADATA_SCHEMA)  # type: ignore[call-arg]
        pq.write_table(metadata_table, self.indices_dir / "embeddings.metadata.parquet")  # type: ignore[call-arg]
    
    def _write_index_metadata(
        self,
        total_conversations: int,
        total_chunks: int,
        *,
        created_at: str | None = None,
        next_vector_id: int | None = None,
    ) -> None:
        if created_at is None:
            created_at = datetime.now().isoformat()
        if next_vector_id is None:
            next_vector_id = total_chunks

        metadata = {
            "schema_version": INDEX_SCHEMA_VERSION,
            "index_format_version": INDEX_FORMAT_VERSION,
            "created_at": created_at,
            "embedding_model": self.config.embedding.model,
            "format": INDEX_FORMAT,
            "last_updated": datetime.now().isoformat(),
            "total_conversations": total_conversations,
            "total_chunks": total_chunks,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "next_vector_id": next_vector_id,
        }

        metadata_path = self.indices_dir / INDEX_METADATA_FILENAME
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
    
    def _has_existing_index(self) -> bool:
        """Check if an existing index is present."""
        metadata_path = self.indices_dir / INDEX_METADATA_FILENAME
        faiss_path = self.indices_dir / "embeddings.faiss"
        has_parquets = any(self.conversations_dir.glob("*.parquet"))

        return metadata_path.exists() or faiss_path.exists() or has_parquets

    def _load_existing_metadata(self) -> dict | None:
        metadata_path = self.indices_dir / INDEX_METADATA_FILENAME
        if not metadata_path.exists():
            return None
        
        with open(metadata_path, 'r') as f:
            return json.load(f)

    def _require_compatible_index(self, metadata: dict) -> None:
        if metadata.get("embedding_model") != self.config.embedding.model:
            raise ValueError(
                f"Model mismatch: index uses '{metadata.get('embedding_model')}', "
                f"config specifies '{self.config.embedding.model}'. "
                "Cannot append with different embedding model."
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
    
    def get_indexed_file_paths(self) -> set:
        """
        Get set of all indexed file paths.

        Returns:
            Set of file path strings that are already in the index
        """
        if self.indexed_paths_path.exists():
            table = pq.read_table(self.indexed_paths_path, columns=["file_path"])
            return set(table.column("file_path").to_pylist())

        indexed_paths: set[str] = set()

        for parquet_file in self.conversations_dir.glob("*.parquet"):
            table = pq.read_table(parquet_file, columns=["file_path"])
            indexed_paths.update(table.column("file_path").to_pylist())

        # Backfill the fast path if possible.
        if indexed_paths:
            self._write_indexed_paths(indexed_paths)

        return indexed_paths

    def index_append_only(
        self,
        file_paths: list[str],
        progress: ProgressCallback | None = None,
    ) -> UpdateStats:
        """
        Append-only indexing for new conversation files.

        SAFETY: This method ONLY adds new data. It never modifies or deletes
        existing indexed data. Safe to call even with orphaned parquet data.

        Supports both Claude Code (.jsonl) and Mistral Vibe (.json) files.

        Args:
            file_paths: List of conversation file paths to index
            progress: Optional progress callback

        Returns:
            UpdateStats with indexing results
        """
        if progress is None:
            progress = NullProgressAdapter()
        if not self.config.indexing.enable_connectors:
            raise RuntimeError(
                "Connector loading is disabled. Set indexing.enable_connectors to true."
            )

        progress.update_phase("Processing new conversations")
        start_time = time.time()

        existing_metadata = self._load_existing_metadata()
        if existing_metadata is None:
            raise RuntimeError(
                "No existing index found. Cannot append to non-existent index. "
                "Initial index must exist before append-only mode can be used."
            )

        self._require_compatible_index(existing_metadata)

        # Get already indexed paths to skip duplicates
        existing_paths = self.get_indexed_file_paths()

        # Filter to only truly new files
        new_files = [f for f in file_paths if f not in existing_paths]

        if not new_files:
            return UpdateStats(
                new_conversations=0,
                updated_conversations=0,
                skipped_conversations=len(file_paths),
                update_time_seconds=time.time() - start_time
            )

        # Load existing FAISS index
        faiss_path = self.indices_dir / "embeddings.faiss"
        existing_index = faiss.read_index(str(faiss_path))

        # Load existing metadata
        existing_metadata_table = pq.read_table(
            self.indices_dir / "embeddings.metadata.parquet"
        )
        existing_metadata_df = existing_metadata_table.to_pandas()
        next_vector_id = int(existing_metadata.get("next_vector_id", 0) or 0)
        existing_ids = existing_metadata_table.column("vector_id").to_pylist()
        max_vector_id = max(existing_ids) if existing_ids else -1
        if next_vector_id <= max_vector_id:
            next_vector_id = max_vector_id + 1

        new_embeddings = []
        new_metadata = []
        new_vector_ids: list[int] = []
        new_conversation_records: dict[str, list[ConversationRecord]] = {}
        new_indexed_paths: set[str] = set()
        connector_name_by_file_path: dict[str, str] = {}
        processed_count = 0

        for idx, file_path in enumerate(new_files, 1):
            json_path = Path(file_path)

            if not json_path.exists():
                logger.warning(f"File not found, skipping: {file_path}")
                continue

            try:
                connector = detect_connector(json_path)
            except ValueError as exc:
                progress.update_file_progress(idx, len(new_files), f"unknown | {json_path.name}")
                logger.warning("%s; skipping: %s", exc, file_path)
                continue

            display_name = f"{connector.name} | {json_path.name}"
            progress.update_file_progress(idx, len(new_files), display_name)

            try:
                record = connector.parse(json_path, next_vector_id)

                # Skip conversations with no messages
                if record.message_count == 0:
                    continue

                new_indexed_paths.add(record.file_path)

                connector_name_by_file_path[record.file_path] = connector.name

                project_key = record.project_id
                if project_key not in new_conversation_records:
                    new_conversation_records[project_key] = []
                new_conversation_records[project_key].append(record)

                chunks_with_meta = self._chunk_by_messages(record.messages, record.title)

                # Batch encode all chunks for this conversation
                chunk_embeddings = self._batch_encode_chunks(chunks_with_meta, progress)

                for chunk_idx, (chunk_meta, embedding) in enumerate(zip(chunks_with_meta, chunk_embeddings)):
                    new_embeddings.append(embedding)

                    new_metadata.append({
                        'vector_id': next_vector_id,
                        'conversation_id': record.conversation_id,
                        'project_id': record.project_id,
                        'chunk_index': chunk_idx,
                        'chunk_text': chunk_meta['text'],
                        'message_start_index': chunk_meta['start_message_index'],
                        'message_end_index': chunk_meta['end_message_index'],
                        'created_at': record.created_at
                    })
                    new_vector_ids.append(next_vector_id)
                    next_vector_id += 1

                processed_count += 1

            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}")
                continue

        # Append to FAISS index
        if new_embeddings:
            embeddings_array = np.array(new_embeddings).astype(np.float32)
            id_array = np.asarray(new_vector_ids, dtype=np.int64)
            try:
                existing_index.add_with_ids(embeddings_array, id_array)
                faiss.write_index(existing_index, str(faiss_path))
            except Exception:
                remaining_ids = [
                    int(value)
                    for value in existing_metadata_table.column("vector_id").to_pylist()
                    if value is not None
                ]
                rebuilt_index = self._rebuild_idmap_index(
                    existing_index,
                    remaining_ids,
                    new_embeddings,
                    new_vector_ids,
                )
                faiss.write_index(rebuilt_index, str(faiss_path))

            # Append to metadata parquet
            new_metadata_table = pa.Table.from_pylist(new_metadata, schema=METADATA_SCHEMA)
            combined_metadata = pa.concat_tables([existing_metadata_table, new_metadata_table])
            pq.write_table(combined_metadata, self.indices_dir / "embeddings.metadata.parquet")

        # Append to conversation parquets
        for project_id, records in new_conversation_records.items():
            new_record_dicts = [self._record_to_dict(r) for r in records]
            self._append_record_dicts(project_id, new_record_dicts)

            code_rows: list[dict] = []
            for record in records:
                connector_name = connector_name_by_file_path.get(record.file_path)
                if not connector_name:
                    raise RuntimeError(f"Missing connector name for indexed file: {record.file_path}")
                code_rows.extend(self._extract_code_block_dicts(record, connector_name))
            self._append_code_blocks(project_id, code_rows)

        # Update index metadata
        existing_index_metadata = self._load_existing_metadata()
        if existing_index_metadata is None:
            raise RuntimeError("Index metadata missing after append-only update")
        total_conversations = existing_index_metadata["total_conversations"] + processed_count
        total_chunks = existing_index_metadata["total_chunks"] + len(new_embeddings)
        created_at = existing_index_metadata.get("created_at") or datetime.now().isoformat()
        self._write_index_metadata(
            total_conversations,
            total_chunks,
            created_at=created_at,
            next_vector_id=next_vector_id,
        )

        progress.update_stats(
            conversations=processed_count,
            chunks=len(new_embeddings),
            embeddings=len(new_embeddings)
        )
        progress.finish()

        if new_indexed_paths:
            self._write_indexed_paths(existing_paths | new_indexed_paths)

        if new_conversation_records:
            file_state = self._load_file_state()
            if not file_state:
                file_state = self._backfill_file_state()
            for records in new_conversation_records.values():
                for record in records:
                    path_obj = Path(record.file_path)
                    file_size = path_obj.stat().st_size if path_obj.exists() else 0
                    connector_name = connector_name_by_file_path.get(record.file_path)
                    if not connector_name:
                        raise RuntimeError(f"Missing connector name for indexed file: {record.file_path}")
                    file_state[record.file_path] = {
                        "file_path": record.file_path,
                        "file_hash": record.file_hash,
                        "file_size": file_size,
                        "indexed_at": record.indexed_at,
                        "connector_name": connector_name,
                        "conversation_id": record.conversation_id,
                        "project_id": record.project_id,
                    }
            self._write_file_state(list(file_state.values()))

        elapsed = time.time() - start_time

        return UpdateStats(
            new_conversations=processed_count,
            updated_conversations=0,
            skipped_conversations=len(file_paths) - processed_count,
            update_time_seconds=elapsed
        )

    def index_adaptive(
        self,
        file_paths: list[str],
        progress: ProgressCallback | None = None,
    ) -> UpdateStats:
        """
        Adaptive indexing for new and modified conversation files.

        New files are appended. Modified files trigger per-conversation reindexing.
        """
        if progress is None:
            progress = NullProgressAdapter()
        if not self.config.indexing.enable_connectors:
            raise RuntimeError(
                "Connector loading is disabled. Set indexing.enable_connectors to true."
            )
        if not self.config.indexing.enable_adaptive_indexing:
            return self.index_append_only(file_paths, progress)

        progress.update_phase("Processing conversations")
        start_time = time.time()

        existing_metadata = self._load_existing_metadata()
        if existing_metadata is None:
            raise RuntimeError(
                "No existing index found. Cannot perform adaptive update. "
                "Initial index must exist before adaptive mode can be used."
            )

        self._require_compatible_index(existing_metadata)

        faiss_path = self.indices_dir / "embeddings.faiss"
        existing_index = faiss.read_index(str(faiss_path))

        existing_metadata_table = pq.read_table(
            self.indices_dir / "embeddings.metadata.parquet"
        )

        file_state = self._load_file_state()
        if not file_state:
            file_state = self._backfill_file_state()

        next_vector_id = int(existing_metadata.get("next_vector_id", 0) or 0)
        existing_ids = existing_metadata_table.column("vector_id").to_pylist()
        max_vector_id = max(existing_ids) if existing_ids else -1
        if next_vector_id <= max_vector_id:
            next_vector_id = max_vector_id + 1

        new_embeddings: list[np.ndarray] = []
        new_metadata: list[dict] = []
        new_vector_ids: list[int] = []
        records_to_append: dict[str, list[ConversationRecord]] = {}
        removed_vector_ids: set[int] = set()
        connector_name_by_file_path: dict[str, str] = {}

        new_count = 0
        updated_count = 0
        skipped_count = 0

        for idx, file_path in enumerate(file_paths, 1):
            json_path = Path(file_path)
            if not json_path.exists():
                logger.warning(f"File not found, skipping: {file_path}")
                skipped_count += 1
                continue

            connector = detect_connector(json_path)
            display_name = f"{connector.name} | {json_path.name}"
            progress.update_file_progress(idx, len(file_paths), display_name)

            file_hash = hashlib.sha256(json_path.read_bytes()).hexdigest()
            file_size = json_path.stat().st_size
            existing_state = file_state.get(file_path)
            if existing_state and existing_state.get("file_hash") == file_hash:
                skipped_count += 1
                continue

            record = connector.parse(json_path, next_vector_id)
            if record.message_count == 0:
                skipped_count += 1
                continue

            old_conversation_id = None
            old_project_id = None
            if existing_state:
                old_conversation_id = existing_state.get("conversation_id")
                old_project_id = existing_state.get("project_id")

            if isinstance(old_conversation_id, str):
                mask = pc.equal(existing_metadata_table["conversation_id"], old_conversation_id)  # type: ignore[attr-defined]
                filtered_rows = existing_metadata_table.filter(mask)
                removed_vector_ids.update(
                    value for value in filtered_rows.column("vector_id").to_pylist() if value is not None
                )
                existing_metadata_table = existing_metadata_table.filter(pc.invert(mask))  # type: ignore[attr-defined]
                if isinstance(old_project_id, str):
                    self._remove_conversation_from_project(old_project_id, old_conversation_id)
                    self._remove_code_blocks_for_conversation(old_project_id, old_conversation_id)
                updated_count += 1
            else:
                new_count += 1

            chunks_with_meta = self._chunk_by_messages(record.messages, record.title)
            record.embedding_id = next_vector_id
            chunk_embeddings = self._batch_encode_chunks(chunks_with_meta, progress)
            for chunk_idx, (chunk_meta, embedding) in enumerate(zip(chunks_with_meta, chunk_embeddings)):
                new_embeddings.append(embedding)
                new_metadata.append({
                    "vector_id": next_vector_id,
                    "conversation_id": record.conversation_id,
                    "project_id": record.project_id,
                    "chunk_index": chunk_idx,
                    "chunk_text": chunk_meta["text"],
                    "message_start_index": chunk_meta["start_message_index"],
                    "message_end_index": chunk_meta["end_message_index"],
                    "created_at": record.created_at,
                })
                new_vector_ids.append(next_vector_id)
                next_vector_id += 1

            records_to_append.setdefault(record.project_id, []).append(record)
            connector_name_by_file_path[record.file_path] = connector.name
            file_state[record.file_path] = {
                "file_path": record.file_path,
                "file_hash": file_hash,
                "file_size": file_size,
                "indexed_at": record.indexed_at,
                "connector_name": connector.name,
                "conversation_id": record.conversation_id,
                "project_id": record.project_id,
            }

        # NOTE: We intentionally do not call `faiss.Index.remove_ids()` here.
        # Several FAISS builds can abort the process on remove_ids for IndexIDMap/IVF
        # combinations, which is not catchable from Python. Instead we make semantic
        # deletion append-only: drop rows from the metadata parquet so stale vectors
        # can no longer join to conversations. This keeps indexing crash-free and
        # preserves the project's "never delete data" safety posture.
        needs_rebuild = False

        if new_embeddings:
            embeddings_array = np.array(new_embeddings).astype(np.float32)
            id_array = np.asarray(new_vector_ids, dtype=np.int64)
            try:
                if not needs_rebuild:
                    existing_index.add_with_ids(embeddings_array, id_array)
                    faiss.write_index(existing_index, str(faiss_path))
            except Exception:
                needs_rebuild = True

        if needs_rebuild:
            remaining_ids = [
                int(value)
                for value in existing_metadata_table.column("vector_id").to_pylist()
                if value is not None
            ]
            rebuilt_index = self._rebuild_idmap_index(
                existing_index,
                remaining_ids,
                new_embeddings,
                new_vector_ids,
            )
            faiss.write_index(rebuilt_index, str(faiss_path))

        if new_metadata or removed_vector_ids:
            filtered_metadata = existing_metadata_table.to_pylist()
            combined_metadata = filtered_metadata + new_metadata
            updated_table = pa.Table.from_pylist(combined_metadata, schema=METADATA_SCHEMA)
            pq.write_table(updated_table, self.indices_dir / "embeddings.metadata.parquet")

        for project_id, records in records_to_append.items():
            record_dicts = [self._record_to_dict(r) for r in records]
            self._append_record_dicts(project_id, record_dicts)

            code_rows: list[dict] = []
            for record in records:
                connector_name = connector_name_by_file_path.get(record.file_path)
                if not connector_name:
                    raise RuntimeError(f"Missing connector name for indexed file: {record.file_path}")
                code_rows.extend(self._extract_code_block_dicts(record, connector_name))
            self._append_code_blocks(project_id, code_rows)

        if file_state:
            self._write_file_state(list(file_state.values()))

        existing_paths = self.get_indexed_file_paths()
        if records_to_append:
            new_paths = {r.file_path for records in records_to_append.values() for r in records}
            if new_paths:
                self._write_indexed_paths(existing_paths | new_paths)

        total_conversations = existing_metadata["total_conversations"] + new_count
        total_chunks = len(existing_metadata_table) + len(new_metadata)
        created_at = existing_metadata.get("created_at") or datetime.now().isoformat()
        self._write_index_metadata(
            total_conversations,
            total_chunks,
            created_at=created_at,
            next_vector_id=next_vector_id,
        )

        progress.update_stats(
            conversations=new_count + updated_count,
            chunks=len(new_metadata),
            embeddings=len(new_metadata),
        )
        progress.finish()

        elapsed = time.time() - start_time

        return UpdateStats(
            new_conversations=new_count,
            updated_conversations=updated_count,
            skipped_conversations=skipped_count,
            update_time_seconds=elapsed,
        )
