import json
import pytest
from pathlib import Path
from searchat.core import ConversationIndexer


@pytest.fixture
def sample_conversation_path(tmp_path):
    conv_file = tmp_path / "test_conv.jsonl"
    lines = [
        {"type": "user", "message": {"text": "Hello"}, "timestamp": "2025-09-01T10:00:00", "uuid": "1"},
        {"type": "assistant", "message": {"text": "Hi there!"}, "timestamp": "2025-09-01T10:00:30", "uuid": "2"}
    ]
    with open(conv_file, 'w', encoding='utf-8') as f:
        for line in lines:
            f.write(json.dumps(line) + '\n')
    return conv_file


def test_process_conversation_basic(sample_conversation_path, tmp_path):
    indexer = ConversationIndexer(tmp_path)
    record = indexer._process_conversation(sample_conversation_path, "project-001", 0)
    
    assert record.conversation_id == "test_conv"
    assert record.project_id == "project-001"
    assert "Hello" in record.title or record.title == "Untitled"
    assert record.message_count == 2
    assert len(record.messages) == 2
    assert "Hello" in record.full_text
    assert "Hi there!" in record.full_text


def test_process_conversation_with_code(tmp_path):
    conv_file = tmp_path / "code_conv.jsonl"
    lines = [
        {"type": "assistant", "message": {"text": "Here's code:\n```python\ndef hello():\n    print('hi')\n```"}, "timestamp": "2025-09-01T10:00:00", "uuid": "1"}
    ]
    with open(conv_file, 'w', encoding='utf-8') as f:
        for line in lines:
            f.write(json.dumps(line) + '\n')
    
    indexer = ConversationIndexer(tmp_path)
    record = indexer._process_conversation(conv_file, "project-001", 0)
    
    assert record.messages[0].has_code
    assert len(record.messages[0].code_blocks) == 1
    assert "def hello()" in record.messages[0].code_blocks[0]


def test_file_hash_generation(sample_conversation_path, tmp_path):
    indexer = ConversationIndexer(tmp_path)
    record = indexer._process_conversation(sample_conversation_path, "project-001", 0)
    
    assert len(record.file_hash) == 64
    assert isinstance(record.file_hash, str)