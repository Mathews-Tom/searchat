from __future__ import annotations

from pathlib import Path

from searchat.core.connectors.aider import AiderConnector


def test_aider_connector_parses_basic_history(tmp_path: Path) -> None:
    history = tmp_path / ".aider.chat.history.md"
    history.write_text(
        "\n".join(
            [
                "#### user:",
                "How do I print?",
                "",
                "#### assistant:",
                "Use print:",
                "```python",
                "print(123)",
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )

    connector = AiderConnector()
    record = connector.parse(history, embedding_id=7)

    assert record.conversation_id
    assert record.project_id.startswith("aider-")
    assert record.message_count == 2
    assert record.messages[0].role == "user"
    assert "print" in record.messages[0].content
    assert record.messages[1].role == "assistant"
    assert record.messages[1].has_code is True
    assert record.messages[1].code_blocks == ["print(123)\n"]
