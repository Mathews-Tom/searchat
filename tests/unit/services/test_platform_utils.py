"""Tests for searchat.services.platform_utils.PlatformManager."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from searchat.services.platform_utils import PlatformManager


@pytest.fixture
def mgr_macos(monkeypatch) -> PlatformManager:
    """PlatformManager that thinks it's on macOS."""
    monkeypatch.setattr(
        "searchat.config.path_resolver.PathResolver.detect_platform",
        staticmethod(lambda: "macos"),
    )
    return PlatformManager()


@pytest.fixture
def mgr_linux(monkeypatch) -> PlatformManager:
    """PlatformManager that thinks it's on Linux."""
    monkeypatch.setattr(
        "searchat.config.path_resolver.PathResolver.detect_platform",
        staticmethod(lambda: "linux"),
    )
    return PlatformManager()


@pytest.fixture
def mgr_windows(monkeypatch) -> PlatformManager:
    """PlatformManager that thinks it's on Windows."""
    monkeypatch.setattr(
        "searchat.config.path_resolver.PathResolver.detect_platform",
        staticmethod(lambda: "windows"),
    )
    return PlatformManager()


@pytest.fixture
def mgr_wsl(monkeypatch) -> PlatformManager:
    """PlatformManager that thinks it's on WSL."""
    monkeypatch.setattr(
        "searchat.config.path_resolver.PathResolver.detect_platform",
        staticmethod(lambda: "wsl"),
    )
    return PlatformManager()


class TestPlatformDetection:
    """Verify PlatformManager sets flags correctly."""

    def test_macos_flags(self, mgr_macos):
        assert mgr_macos.is_macos is True
        assert mgr_macos.is_windows is False
        assert mgr_macos.is_wsl is False
        assert mgr_macos.is_linux is False

    def test_linux_flags(self, mgr_linux):
        assert mgr_linux.is_linux is True
        assert mgr_linux.is_macos is False

    def test_windows_flags(self, mgr_windows):
        assert mgr_windows.is_windows is True
        assert mgr_windows.is_linux is False

    def test_wsl_flags(self, mgr_wsl):
        assert mgr_wsl.is_wsl is True
        assert mgr_wsl.is_windows is False


class TestTranslateCwdIfNeeded:
    """Tests for PlatformManager._translate_cwd_if_needed."""

    def test_none_input(self, mgr_macos):
        assert mgr_macos._translate_cwd_if_needed(None) is None

    def test_empty_string(self, mgr_macos):
        assert mgr_macos._translate_cwd_if_needed("") is None

    def test_macos_passthrough(self, mgr_macos):
        assert mgr_macos._translate_cwd_if_needed("/Users/test") == "/Users/test"

    def test_windows_passthrough(self, mgr_windows):
        assert mgr_windows._translate_cwd_if_needed("C:\\Users\\test") == "C:\\Users\\test"

    def test_wsl_translates_windows_path(self, mgr_wsl):
        result = mgr_wsl._translate_cwd_if_needed("C:\\Users\\test")
        # Path separator varies by OS; normalize for comparison
        assert result is not None
        assert result.replace("\\", "/") == "/mnt/c/Users/test"

    def test_wsl_unix_path_passthrough(self, mgr_wsl):
        assert mgr_wsl._translate_cwd_if_needed("/home/user") == "/home/user"


class TestNormalizePath:
    """Tests for PlatformManager.normalize_path."""

    def test_windows_no_change(self, mgr_windows):
        assert mgr_windows.normalize_path("C:\\Users\\test") == "C:\\Users\\test"

    def test_unix_converts_backslashes(self, mgr_linux):
        assert mgr_linux.normalize_path("path\\to\\file") == "path/to/file"

    def test_macos_converts_backslashes(self, mgr_macos):
        assert mgr_macos.normalize_path("a\\b\\c") == "a/b/c"


class TestDetectWslPath:
    """Tests for PlatformManager.detect_wsl_path."""

    def test_not_windows_always_false(self, mgr_linux):
        assert mgr_linux.detect_wsl_path("/home/user") is False

    def test_windows_home_path(self, mgr_windows):
        assert mgr_windows.detect_wsl_path("/home/user") is True

    def test_windows_mnt_path(self, mgr_windows):
        assert mgr_windows.detect_wsl_path("/mnt/c/Users") is True

    def test_windows_unc_wsl_path(self, mgr_windows):
        assert mgr_windows.detect_wsl_path("\\\\wsl$\\Ubuntu\\home") is True

    def test_windows_native_path_not_wsl(self, mgr_windows):
        assert mgr_windows.detect_wsl_path("C:\\Users\\test") is False


class TestOpenTerminalWithCommand:
    """Tests for open_terminal_with_command dispatching."""

    @patch("subprocess.Popen")
    def test_macos_uses_osascript(self, mock_popen, mgr_macos):
        mock_popen.return_value = MagicMock()
        mgr_macos.open_terminal_with_command("echo hello", cwd="/tmp")
        args = mock_popen.call_args[0][0]
        assert args[0] == "osascript"

    @patch("subprocess.Popen")
    def test_macos_no_cwd(self, mock_popen, mgr_macos):
        mock_popen.return_value = MagicMock()
        mgr_macos.open_terminal_with_command("echo hello")
        args = mock_popen.call_args[0][0]
        assert args[0] == "osascript"

    @patch("subprocess.Popen")
    def test_linux_uses_gnome_terminal(self, mock_popen, mgr_linux):
        mock_popen.return_value = MagicMock()
        mgr_linux.open_terminal_with_command("echo hello")
        args = mock_popen.call_args[0][0]
        assert args[0] == "gnome-terminal"

    @patch("subprocess.Popen")
    def test_linux_with_cwd(self, mock_popen, mgr_linux):
        mock_popen.return_value = MagicMock()
        mgr_linux.open_terminal_with_command("echo hello", cwd="/tmp/test")
        args = mock_popen.call_args[0][0]
        assert "cd" in " ".join(args)

    @patch("subprocess.Popen")
    def test_windows_native_cwd(self, mock_popen, mgr_windows):
        mock_popen.return_value = MagicMock()
        mgr_windows.open_terminal_with_command("echo hello", cwd="C:\\Users")
        args = mock_popen.call_args[0][0]
        assert "cmd.exe" in args

    @patch("subprocess.Popen")
    def test_windows_wsl_cwd(self, mock_popen, mgr_windows):
        mock_popen.return_value = MagicMock()
        mgr_windows.open_terminal_with_command("echo hello", cwd="/home/user")
        args = mock_popen.call_args[0][0]
        assert "wsl.exe" in args

    @patch("subprocess.Popen")
    def test_windows_no_cwd(self, mock_popen, mgr_windows):
        mock_popen.return_value = MagicMock()
        mgr_windows.open_terminal_with_command("echo hello")
        args = mock_popen.call_args[0][0]
        assert "cmd.exe" in args

    @patch("subprocess.Popen")
    def test_wsl_with_cwd(self, mock_popen, mgr_wsl):
        mock_popen.return_value = MagicMock()
        mgr_wsl.open_terminal_with_command("echo hello", cwd="/home/user")
        args = mock_popen.call_args[0][0]
        assert args[0] == "bash"

    @patch("subprocess.Popen")
    def test_wsl_no_cwd(self, mock_popen, mgr_wsl):
        mock_popen.return_value = MagicMock()
        mgr_wsl.open_terminal_with_command("echo hello")
        args = mock_popen.call_args[0][0]
        assert args[0] == "bash"

    def test_unsupported_platform_raises(self, monkeypatch):
        monkeypatch.setattr(
            "searchat.config.path_resolver.PathResolver.detect_platform",
            staticmethod(lambda: "unknown"),
        )
        mgr = PlatformManager()
        with pytest.raises(NotImplementedError, match="Unsupported platform"):
            mgr.open_terminal_with_command("echo hello")
