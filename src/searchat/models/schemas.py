"""PyArrow schemas for Parquet storage."""
from __future__ import annotations

import pyarrow as pa


CONVERSATION_SCHEMA = pa.schema([
    ('conversation_id', pa.string()),
    ('project_id', pa.string()),
    ('file_path', pa.string()),
    ('title', pa.string()),
    ('created_at', pa.timestamp('us')),
    ('updated_at', pa.timestamp('us')),
    ('message_count', pa.int32()),
    ('messages', pa.list_(
        pa.struct([
            ('sequence', pa.int32()),
            ('role', pa.string()),
            ('content', pa.string()),
            ('timestamp', pa.timestamp('us')),
            ('has_code', pa.bool_()),
            ('code_blocks', pa.list_(pa.string()))
        ])
    )),
    ('full_text', pa.string()),
    ('embedding_id', pa.int64()),
    ('file_hash', pa.string()),
    ('indexed_at', pa.timestamp('us')),
    ('files_mentioned', pa.list_(pa.string())),
    ('git_branch', pa.string())
])

METADATA_SCHEMA = pa.schema([
    ('vector_id', pa.int64()),
    ('conversation_id', pa.string()),
    ('project_id', pa.string()),
    ('chunk_index', pa.int32()),
    ('chunk_text', pa.string()),
    ('message_start_index', pa.int32()),
    ('message_end_index', pa.int32()),
    ('created_at', pa.timestamp('us'))
])

FILE_STATE_SCHEMA = pa.schema([
    ('file_path', pa.string()),
    ('file_hash', pa.string()),
    ('file_size', pa.int64()),
    ('indexed_at', pa.timestamp('us')),
    ('connector_name', pa.string()),
    ('conversation_id', pa.string()),
    ('project_id', pa.string()),
])


CODE_BLOCK_SCHEMA = pa.schema([
    ("conversation_id", pa.string()),
    ("project_id", pa.string()),
    ("connector", pa.string()),
    ("file_path", pa.string()),
    ("title", pa.string()),
    ("conversation_created_at", pa.timestamp("us")),
    ("conversation_updated_at", pa.timestamp("us")),
    ("message_index", pa.int32()),
    ("block_index", pa.int32()),
    ("role", pa.string()),
    ("message_timestamp", pa.timestamp("us")),
    ("fence_language", pa.string()),
    ("language", pa.string()),
    ("language_source", pa.string()),
    ("functions", pa.list_(pa.string())),
    ("classes", pa.list_(pa.string())),
    ("imports", pa.list_(pa.string())),
    ("code", pa.string()),
    ("code_hash", pa.string()),
    ("lines", pa.int32()),
])
