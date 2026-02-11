"""Tests for searchat.config.path_resolver.PathResolver."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from searchat.config.path_resolver import PathResolver

# Save original staticmethod descriptors before conftest autouse fixtures
# patch them with empty lambdas at test runtime.
_orig_resolve_opencode = PathResolver.__dict__["resolve_opencode_dirs"]
_orig_resolve_codex = PathResolver.__dict__["resolve_codex_dirs"]
_orig_resolve_gemini = PathResolver.__dict__["resolve_gemini_dirs"]
_orig_resolve_continue = PathResolver.__dict__["resolve_continue_dirs"]
_orig_resolve_cursor = PathResolver.__dict__["resolve_cursor_dirs"]
_orig_resolve_aider = PathResolver.__dict__["resolve_aider_dirs"]


def _restore(monkeypatch, name: str, original: object) -> None:
    """Re-apply an original staticmethod descriptor to PathResolver."""
    monkeypatch.setattr(PathResolver, name, original)


class TestExpandPathTemplate:
    """Tests for PathResolver.expand_path_template."""

    def test_expands_home_placeholder(self):
        result = PathResolver.expand_path_template("{home}/data")
        assert result == f"{Path.home()}/data"

    def test_expands_username_placeholder(self, monkeypatch):
        monkeypatch.setenv("USER", "testuser")
        result = PathResolver.expand_path_template("{username}/dir")
        assert result.startswith("testuser/")

    def test_expands_tilde(self):
        result = PathResolver.expand_path_template("~/data")
        assert not result.startswith("~")
        assert result.endswith("/data")

    def test_expands_env_vars(self, monkeypatch):
        monkeypatch.setenv("MY_DIR", "/custom/path")
        result = PathResolver.expand_path_template("$MY_DIR/sub")
        assert result == "/custom/path/sub"

    def test_no_placeholders_passthrough(self):
        result = PathResolver.expand_path_template("/absolute/path")
        assert result == "/absolute/path"


class TestDetectPlatform:
    """Tests for PathResolver.detect_platform."""

    def test_darwin(self, monkeypatch):
        monkeypatch.setattr("sys.platform", "darwin")
        assert PathResolver.detect_platform() == "macos"

    def test_win32(self, monkeypatch):
        monkeypatch.setattr("sys.platform", "win32")
        assert PathResolver.detect_platform() == "windows"

    def test_linux_no_wsl(self, monkeypatch):
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.setattr(
            PathResolver, "_is_wsl", staticmethod(lambda: False)
        )
        assert PathResolver.detect_platform() == "linux"

    def test_linux_with_wsl(self, monkeypatch):
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.setattr(
            PathResolver, "_is_wsl", staticmethod(lambda: True)
        )
        assert PathResolver.detect_platform() == "wsl"

    def test_unknown_platform(self, monkeypatch):
        monkeypatch.setattr("sys.platform", "freebsd12")
        assert PathResolver.detect_platform() == "unknown"


class TestIsWsl:
    """Tests for PathResolver._is_wsl."""

    def test_not_wsl_when_proc_version_missing(self):
        # _is_wsl reads /proc/version; on macOS it doesn't exist -> False
        assert PathResolver._is_wsl() is False

    def test_wsl_detected_from_proc_version(self):
        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = lambda *a: None
            mock_open.return_value.read = lambda: "Linux version 5.15.0 (microsoft-standard-WSL)"
            assert PathResolver._is_wsl() is True


class TestTranslateClaudePath:
    """Tests for PathResolver.translate_claude_path."""

    def test_no_translation_on_macos(self, monkeypatch):
        monkeypatch.setattr(PathResolver, "detect_platform", staticmethod(lambda: "macos"))
        result = PathResolver.translate_claude_path("/Users/testuser/.claude")
        assert result == Path("/Users/testuser/.claude")

    def test_windows_path_to_wsl_mount(self, monkeypatch):
        monkeypatch.setattr(PathResolver, "detect_platform", staticmethod(lambda: "wsl"))
        result = PathResolver.translate_claude_path("C:\\Users\\test\\.claude")
        assert result == Path("/mnt/c/Users/test/.claude")

    def test_windows_forward_slash_to_wsl(self, monkeypatch):
        monkeypatch.setattr(PathResolver, "detect_platform", staticmethod(lambda: "wsl"))
        result = PathResolver.translate_claude_path("D:/Projects/data")
        assert result == Path("/mnt/d/Projects/data")

    def test_wsl_mount_to_windows(self, monkeypatch):
        monkeypatch.setattr(PathResolver, "detect_platform", staticmethod(lambda: "windows"))
        result = PathResolver.translate_claude_path("/mnt/c/Users/test")
        assert str(result) == "C:\\Users\\test"

    def test_wsl_mount_drive_only(self, monkeypatch):
        monkeypatch.setattr(PathResolver, "detect_platform", staticmethod(lambda: "windows"))
        result = PathResolver.translate_claude_path("/mnt/c")
        assert str(result) == "C:\\"

    def test_wsl_unc_path_on_windows(self, monkeypatch):
        monkeypatch.setattr(PathResolver, "detect_platform", staticmethod(lambda: "windows"))
        unc = "\\\\wsl$\\Ubuntu\\home\\user"
        result = PathResolver.translate_claude_path(unc)
        assert result == Path(unc)


class TestGetSharedSearchDir:
    """Tests for PathResolver.get_shared_search_dir."""

    def test_env_var_takes_priority(self, monkeypatch, tmp_path):
        data_dir = tmp_path / "env_data"
        data_dir.mkdir()
        monkeypatch.setenv("SEARCHAT_DATA_DIR", str(data_dir))
        result = PathResolver.get_shared_search_dir()
        assert result == data_dir

    def test_falls_back_to_config(self, monkeypatch, tmp_path):
        monkeypatch.delenv("SEARCHAT_DATA_DIR", raising=False)
        from searchat.config import Config
        config = Config.load()
        result = PathResolver.get_shared_search_dir(config)
        assert isinstance(result, Path)


class TestEnsureDirectory:
    """Tests for PathResolver.ensure_directory."""

    def test_creates_nested_directory(self, tmp_path):
        target = tmp_path / "a" / "b" / "c"
        result = PathResolver.ensure_directory(target)
        assert result == target
        assert target.is_dir()

    def test_existing_directory_is_noop(self, tmp_path):
        result = PathResolver.ensure_directory(tmp_path)
        assert result == tmp_path


class TestResolveVibeDirs:
    """Tests for PathResolver.resolve_vibe_dirs."""

    def test_returns_empty_when_no_dirs_exist(self, monkeypatch):
        monkeypatch.delenv("VIBE_HOME", raising=False)
        dirs = PathResolver.resolve_vibe_dirs()
        assert isinstance(dirs, list)

    def test_custom_vibe_home(self, monkeypatch, tmp_path):
        session_dir = tmp_path / "logs" / "session"
        session_dir.mkdir(parents=True)
        monkeypatch.setenv("VIBE_HOME", str(tmp_path))
        dirs = PathResolver.resolve_vibe_dirs()
        assert session_dir in dirs


class TestResolveOpencodeDirs:
    """Tests for PathResolver.resolve_opencode_dirs."""

    def test_env_var_overrides(self, monkeypatch, tmp_path):
        _restore(monkeypatch, "resolve_opencode_dirs", _orig_resolve_opencode)
        monkeypatch.setenv("SEARCHAT_OPENCODE_DATA_DIR", str(tmp_path))
        dirs = PathResolver.resolve_opencode_dirs()
        assert tmp_path in dirs

    def test_empty_when_no_dirs(self, monkeypatch):
        _restore(monkeypatch, "resolve_opencode_dirs", _orig_resolve_opencode)
        monkeypatch.delenv("SEARCHAT_OPENCODE_DATA_DIR", raising=False)
        dirs = PathResolver.resolve_opencode_dirs()
        assert isinstance(dirs, list)


class TestResolveCodexDirs:
    """Tests for PathResolver.resolve_codex_dirs."""

    def test_env_var_overrides(self, monkeypatch, tmp_path):
        _restore(monkeypatch, "resolve_codex_dirs", _orig_resolve_codex)
        monkeypatch.setenv("SEARCHAT_CODEX_DATA_DIR", str(tmp_path))
        dirs = PathResolver.resolve_codex_dirs()
        assert tmp_path in dirs

    def test_codex_home_fallback(self, monkeypatch, tmp_path):
        _restore(monkeypatch, "resolve_codex_dirs", _orig_resolve_codex)
        monkeypatch.delenv("SEARCHAT_CODEX_DATA_DIR", raising=False)
        monkeypatch.setenv("CODEX_HOME", str(tmp_path))
        dirs = PathResolver.resolve_codex_dirs()
        assert tmp_path in dirs


class TestResolveGeminiDirs:
    """Tests for PathResolver.resolve_gemini_dirs."""

    def test_env_var_overrides(self, monkeypatch, tmp_path):
        _restore(monkeypatch, "resolve_gemini_dirs", _orig_resolve_gemini)
        monkeypatch.setenv("SEARCHAT_GEMINI_DATA_DIR", str(tmp_path))
        dirs = PathResolver.resolve_gemini_dirs()
        assert tmp_path in dirs


class TestResolveContinueDirs:
    """Tests for PathResolver.resolve_continue_dirs."""

    def test_env_var_overrides(self, monkeypatch, tmp_path):
        _restore(monkeypatch, "resolve_continue_dirs", _orig_resolve_continue)
        monkeypatch.setenv("SEARCHAT_CONTINUE_DATA_DIR", str(tmp_path))
        dirs = PathResolver.resolve_continue_dirs()
        assert tmp_path in dirs


class TestResolveCursorDirs:
    """Tests for PathResolver.resolve_cursor_dirs."""

    def test_env_var_overrides(self, monkeypatch, tmp_path):
        _restore(monkeypatch, "resolve_cursor_dirs", _orig_resolve_cursor)
        monkeypatch.setenv("SEARCHAT_CURSOR_DATA_DIR", str(tmp_path))
        dirs = PathResolver.resolve_cursor_dirs()
        assert tmp_path in dirs

    def test_linux_fallback_candidate(self, monkeypatch, tmp_path):
        _restore(monkeypatch, "resolve_cursor_dirs", _orig_resolve_cursor)
        monkeypatch.delenv("SEARCHAT_CURSOR_DATA_DIR", raising=False)
        monkeypatch.setattr("platform.system", lambda: "linux")
        candidate = tmp_path / ".config" / "Cursor" / "User"
        candidate.mkdir(parents=True)
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        dirs = PathResolver.resolve_cursor_dirs()
        assert candidate in dirs


class TestResolveAiderDirs:
    """Tests for PathResolver.resolve_aider_dirs."""

    def test_env_var_with_multiple_paths(self, monkeypatch, tmp_path):
        _restore(monkeypatch, "resolve_aider_dirs", _orig_resolve_aider)
        dir_a = tmp_path / "project_a"
        dir_b = tmp_path / "project_b"
        dir_a.mkdir()
        dir_b.mkdir()
        monkeypatch.setenv("SEARCHAT_AIDER_PROJECT_DIRS", f"{dir_a}{os.pathsep}{dir_b}")
        dirs = PathResolver.resolve_aider_dirs()
        assert dir_a in dirs
        assert dir_b in dirs

    def test_empty_when_env_not_set(self, monkeypatch):
        _restore(monkeypatch, "resolve_aider_dirs", _orig_resolve_aider)
        monkeypatch.delenv("SEARCHAT_AIDER_PROJECT_DIRS", raising=False)
        dirs = PathResolver.resolve_aider_dirs()
        assert dirs == []

    def test_skips_nonexistent_paths(self, monkeypatch, tmp_path):
        _restore(monkeypatch, "resolve_aider_dirs", _orig_resolve_aider)
        missing = tmp_path / "nonexistent"
        monkeypatch.setenv("SEARCHAT_AIDER_PROJECT_DIRS", str(missing))
        dirs = PathResolver.resolve_aider_dirs()
        assert dirs == []


class TestResolveClaudeDirs:
    """Tests for PathResolver.resolve_claude_dirs."""

    def test_raises_when_no_dirs_found(self, monkeypatch, tmp_path):
        monkeypatch.delenv("SEARCHAT_ADDITIONAL_DIRS", raising=False)
        monkeypatch.setattr(PathResolver, "detect_platform", staticmethod(lambda: "linux"))
        from searchat.config import Config
        config = Config.load()
        monkeypatch.setattr(
            config.paths, "claude_directory_windows",
            str(tmp_path / "nonexistent_win"),
        )
        monkeypatch.setattr(
            config.paths, "claude_directory_wsl",
            str(tmp_path / "nonexistent_wsl"),
        )
        monkeypatch.setattr(
            "searchat.config.path_resolver.CLAUDE_DIR_CANDIDATES", [],
        )
        with pytest.raises(RuntimeError, match="No Claude conversation directories found"):
            PathResolver.resolve_claude_dirs(config)

    def test_additional_dirs_from_env(self, monkeypatch, tmp_path):
        extra = tmp_path / "extra_claude"
        extra.mkdir()
        monkeypatch.setenv("SEARCHAT_ADDITIONAL_DIRS", str(extra))
        monkeypatch.setattr(PathResolver, "detect_platform", staticmethod(lambda: "linux"))
        from searchat.config import Config
        config = Config.load()
        dirs = PathResolver.resolve_claude_dirs(config)
        assert extra in dirs
