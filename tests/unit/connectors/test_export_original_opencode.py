"""Round-trip tests for `OpenCodeConnector.export_original` via
`services.source_lifecycle.verify_roundtrip` (M8).

Writes a real OpenCode session JSON at its real on-disk location
(`storage/session/<projectID>/<sessionID>.json`) alongside real sibling
`storage/message/<sessionID>/*.json` files -- the on-disk shape
`OpenCodeConnector.parse` reads first via `_load_opencode_messages`.
`verify_roundtrip` mirrors only the exported session file itself into a
throwaway temp dir (never the sibling message directory), so re-parsing it
there can only succeed through `export_original`'s inline `messages`
fallback -- proving that fallback, not the sibling-file path, reconstructs
the conversation. No mocking of `connector.parse`,
`connector.export_original`, or `verify_roundtrip` itself.
"""
from __future__ import annotations

import json

import pytest

from searchat.core.connectors.opencode import OpenCodeConnector
from searchat.services.source_lifecycle import verify_roundtrip


@pytest.fixture
def connector() -> OpenCodeConnector:
    return OpenCodeConnector()


class TestOpenCodeExportOriginalRoundtrip:
    def test_roundtrip_inline_messages_fallback_when_sibling_dirs_absent(
        self, connector: OpenCodeConnector, tmp_path
    ) -> None:
        session_id = "ses_7e2c9a"
        project_id = "proj-9d1"

        # Real on-disk layout: storage/session/<projectID>/<sessionID>.json
        session_dir = tmp_path / "storage" / "session" / project_id
        session_dir.mkdir(parents=True)
        session_data = {
            "id": session_id,
            "sessionID": session_id,
            "projectID": project_id,
            "title": "Fix the fibonacci helper",
            "time": {"created": 1750000000000, "updated": 1750000100000},
        }
        session_path = session_dir / f"{session_id}.json"
        session_path.write_text(json.dumps(session_data), encoding="utf-8")

        # Real on-disk layout: sibling storage/message/<sessionID>/*.json.
        # This is what the ORIGINAL parse() reads -- session_data itself
        # deliberately carries no inline "messages" key.
        message_dir = tmp_path / "storage" / "message" / session_id
        message_dir.mkdir(parents=True)
        (message_dir / "msg1.json").write_text(
            json.dumps(
                {
                    "id": "msg1",
                    "role": "user",
                    "content": "How do I write a fast fibonacci function?",
                    "time": {"created": 1750000000000},
                }
            ),
            encoding="utf-8",
        )
        (message_dir / "msg2.json").write_text(
            json.dumps(
                {
                    "id": "msg2",
                    "role": "assistant",
                    "content": "Use memoization to avoid recomputation.",
                    "time": {"created": 1750000050000},
                }
            ),
            encoding="utf-8",
        )

        record = connector.parse(session_path, embedding_id=0)

        # Sanity: the original parse actually pulled messages from the
        # sibling files (session_data has no inline "messages" key at all),
        # so this is a genuine test of the sibling-dir-reliant on-disk shape.
        assert record.message_count == 2
        assert [m.role for m in record.messages] == ["user", "assistant"]
        assert record.messages[0].content == "How do I write a fast fibonacci function?"
        assert record.messages[1].content == "Use memoization to avoid recomputation."

        exported = connector.export_original(record)
        assert isinstance(exported, bytes)
        assert exported
        exported_payload = json.loads(exported)
        # export_original must embed messages inline -- this is the only
        # data verify_roundtrip's temp-mirrored re-parse can rely on, since
        # the sibling storage/message directory is never mirrored.
        assert exported_payload.get("messages")

        result = verify_roundtrip(connector, record)
        assert result.ok is True, result.reason
        assert result.mismatches == ()
