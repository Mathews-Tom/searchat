"""Unit tests for `AiderConnector.export_original` / round-trip verification (M8).

Aider's `.aider.chat.history.md` format carries no session identity or
timestamp of its own: `conversation_id` is `sha256(str(path.resolve()))[:16]`
and every message/record timestamp is the file's OWN `st_mtime` at parse
time (see `AiderConnector.export_original`'s docstring). `verify_roundtrip`
always re-parses the exported bytes at a different, throwaway mirrored
path, so those path/mtime-derived fields can never match -- the round trip
must honestly fail rather than silently reporting success. Message content
and title, which ARE derived from file content, must still be faithfully
reconstructed -- verified separately here by calling `export_original`
directly and comparing role+content pairs (excluding the legitimately
mtime-derived timestamps).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from searchat.core.connectors.aider import AiderConnector
from searchat.services.source_lifecycle import verify_roundtrip

_HISTORY_MD = """#### user
How do I write a for loop in Python?

#### assistant
Use `for item in iterable:` syntax.

```python
for item in [1, 2, 3]:
    print(item)
```
"""


@pytest.fixture
def connector() -> AiderConnector:
    return AiderConnector()


def _write_history(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ".aider.chat.history.md"
    path.write_text(_HISTORY_MD, encoding="utf-8")
    return path


class TestAiderRoundtripConversationIdMismatch:
    """`conversation_id` is a hash of the file's own absolute path, and
    `verify_roundtrip` always re-parses at a different (mirrored) path --
    so the round trip must fail, honestly reporting `conversation_id` as a
    mismatch rather than a silent false success."""

    def test_roundtrip_fails_with_conversation_id_mismatch(
        self, connector: AiderConnector, tmp_path: Path
    ) -> None:
        path = _write_history(tmp_path / "myproject")
        record = connector.parse(path, embedding_id=0)

        result = verify_roundtrip(connector, record)

        assert result.ok is False
        assert "conversation_id" in result.mismatches


class TestAiderExportPreservesMessagesAndTitle:
    """Despite the identity/timestamp limitation above, message content and
    title ARE faithfully reconstructed by `export_original` -- verified
    directly here (bypassing `verify_roundtrip`, which would otherwise also
    flag the expected, documented timestamp/id divergence) by comparing
    role+content pairs and title only, deliberately excluding the
    legitimately mtime-derived timestamps.
    """

    def test_export_then_reparse_preserves_role_content_and_title(
        self, connector: AiderConnector, tmp_path: Path
    ) -> None:
        path = _write_history(tmp_path / "original")
        record = connector.parse(path, embedding_id=0)

        exported = connector.export_original(record)
        assert exported

        relocated_dir = tmp_path / "relocated"
        relocated_dir.mkdir(parents=True, exist_ok=True)
        new_path = relocated_dir / ".aider.chat.history.md"
        new_path.write_bytes(exported)
        reparsed = connector.parse(new_path, embedding_id=0)

        original_pairs = [(m.role, m.content) for m in record.messages]
        reparsed_pairs = [(m.role, m.content) for m in reparsed.messages]
        assert original_pairs == reparsed_pairs
        assert reparsed.title == record.title
