from __future__ import annotations

from searchat.daemon.ghost import extract_signatures


def test_extract_signatures_detects_traceback_tail() -> None:
    text = """line1
Traceback (most recent call last):
  File \"x.py\", line 1, in <module>
    boom()
ValueError: bad
"""
    sigs = extract_signatures(text)
    assert sigs
    assert "ValueError: bad" in sigs[0]


def test_extract_signatures_empty_when_no_patterns() -> None:
    sigs = extract_signatures("hello world\nall good\n")
    assert sigs == []
