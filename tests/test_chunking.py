import pytest
from pathlib import Path
from searchat.core import ConversationIndexer


def test_chunk_text_basic(tmp_path):
    indexer = ConversationIndexer(tmp_path)
    text = "a" * 1500
    chunks = indexer._chunk_text(text, chunk_size=1000, overlap=200)
    
    assert len(chunks) == 2
    assert len(chunks[0]) == 1000
    assert len(chunks[1]) <= 1000


def test_chunk_text_with_overlap(tmp_path):
    indexer = ConversationIndexer(tmp_path)
    text = "0123456789" * 150
    chunks = indexer._chunk_text(text, chunk_size=1000, overlap=200)
    
    for i in range(len(chunks) - 1):
        overlap_start = chunks[i][-200:]
        overlap_end = chunks[i+1][:200]
        assert overlap_start == overlap_end


def test_chunk_text_short_text(tmp_path):
    indexer = ConversationIndexer(tmp_path)
    text = "short text"
    chunks = indexer._chunk_text(text, chunk_size=1000, overlap=200)
    
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_empty(tmp_path):
    indexer = ConversationIndexer(tmp_path)
    text = ""
    chunks = indexer._chunk_text(text, chunk_size=1000, overlap=200)
    
    assert len(chunks) == 1
    assert chunks[0] == ""