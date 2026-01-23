"""PyArrow schemas for Parquet storage."""
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
    ('indexed_at', pa.timestamp('us'))
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
