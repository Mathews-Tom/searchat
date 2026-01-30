from searchat.api.utils import detect_tool_from_path


def test_detect_tool_from_path_claude():
    assert detect_tool_from_path("/tmp/conv.jsonl") == "claude"


def test_detect_tool_from_path_opencode():
    assert detect_tool_from_path("/home/user/.local/share/opencode/storage/session/abc.json") == "opencode"


def test_detect_tool_from_path_vibe_default():
    assert detect_tool_from_path("/home/user/.vibe/logs/session/session.json") == "vibe"
