"""Tests for searchat.config.settings edge cases."""
from __future__ import annotations

from pathlib import Path

import pytest

from searchat.config import Config


class TestConfigLoad:
    """Tests for Config.load edge cases."""

    def test_explicit_missing_path_raises(self, tmp_path):
        """Config.load with explicit nonexistent path raises FileNotFoundError."""
        missing = tmp_path / "nonexistent" / "settings.toml"
        with pytest.raises(FileNotFoundError):
            Config.load(config_path=missing)

    def test_default_load_succeeds(self):
        """Config.load without explicit path falls back to defaults."""
        config = Config.load()
        assert config is not None
        assert config.paths is not None
