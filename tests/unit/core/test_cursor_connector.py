import json
import sqlite3
from pathlib import Path

from searchat.core.connectors.cursor import CursorConnector


def test_cursor_connector_parses_minimal_sqlite(tmp_path: Path) -> None:
    db_path = tmp_path / "state.vscdb"

    con = sqlite3.connect(db_path)
    try:
        con.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")

        composer_id = "composer-1"
        bubble_1 = "bubble-1"
        bubble_2 = "bubble-2"

        composer = {
            "_v": 3,
            "composerId": composer_id,
            "createdAt": 1_700_000_000_000,
            "lastUpdatedAt": 1_700_000_010_000,
            "fullConversationHeadersOnly": [
                {"bubbleId": bubble_1, "type": 1},
                {"bubbleId": bubble_2, "type": 2},
            ],
        }

        con.execute(
            "INSERT INTO ItemTable(key, value) VALUES(?, ?)",
            (f"composerData:{composer_id}", json.dumps(composer)),
        )

        bubble_one = {
            "_v": 2,
            "bubbleId": bubble_1,
            "type": 1,
            "rawText": "Hello from user",
            "timestamp": 1_700_000_000_000,
        }
        bubble_two = {
            "_v": 2,
            "bubbleId": bubble_2,
            "type": 2,
            "rawText": "Hello from assistant",
            "timingInfo": {"clientEndTime": 1_700_000_005_000},
        }

        con.execute(
            "INSERT INTO ItemTable(key, value) VALUES(?, ?)",
            (f"bubble:{bubble_1}", json.dumps(bubble_one)),
        )
        con.execute(
            "INSERT INTO ItemTable(key, value) VALUES(?, ?)",
            (f"bubble:{bubble_2}", json.dumps(bubble_two)),
        )

        con.commit()
    finally:
        con.close()

    connector = CursorConnector()
    pseudo = Path(f"{db_path.as_posix()}.cursor/{composer_id}.json")
    record = connector.parse(pseudo, embedding_id=0)

    assert record.conversation_id == composer_id
    assert record.project_id.startswith("cursor-")
    assert record.message_count == 2
    assert record.messages[0].role == "user"
    assert record.messages[0].content == "Hello from user"
    assert record.messages[1].role == "assistant"
    assert record.messages[1].content == "Hello from assistant"
