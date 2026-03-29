"""Tests for palace and distillation config."""
from __future__ import annotations

import os
from unittest.mock import patch

from searchat.config.settings import DistillationConfig, PalaceConfig


class TestDistillationConfig:
    def test_default_values(self):
        config = DistillationConfig.from_dict({})
        assert config.provider == "auto"
        assert config.cli_model == "claude-haiku-4-5-20251001"
        assert config.batch_size == 10
        assert config.max_ply_length == 20
        assert config.min_exchange_chars == 50

    def test_from_dict(self):
        config = DistillationConfig.from_dict({
            "provider": "claude",
            "cli_model": "claude-sonnet-4-6",
            "batch_size": 5,
            "max_ply_length": 30,
            "min_exchange_chars": 100,
        })
        assert config.provider == "claude"
        assert config.cli_model == "claude-sonnet-4-6"
        assert config.batch_size == 5
        assert config.max_ply_length == 30
        assert config.min_exchange_chars == 100

    def test_invalid_provider_falls_back(self):
        config = DistillationConfig.from_dict({"provider": "invalid_provider"})
        assert config.provider == "auto"

    def test_env_var_override(self):
        with patch.dict(os.environ, {"SEARCHAT_DISTILLATION_PROVIDER": "openai"}):
            config = DistillationConfig.from_dict({})
            assert config.provider == "openai"


class TestPalaceConfig:
    def test_default_disabled(self):
        config = PalaceConfig.from_dict({})
        assert config.enabled is False

    def test_enabled(self):
        config = PalaceConfig.from_dict({"enabled": True})
        assert config.enabled is True

    def test_env_var_override(self):
        with patch.dict(os.environ, {"SEARCHAT_PALACE_ENABLED": "true"}):
            config = PalaceConfig.from_dict({})
            assert config.enabled is True


class TestConfigLoad:
    def test_config_has_palace_and_distillation(self):
        from searchat.config import Config

        config = Config.load()
        assert hasattr(config, "palace")
        assert hasattr(config, "distillation")
        assert config.palace.enabled is False  # default
        assert config.distillation.provider in {"auto", "claude", "openai"}
