"""Tests for searchat.llm.model_presets."""
from __future__ import annotations

import pytest

from searchat.llm.model_presets import (
    ModelPreset,
    DEFAULT_PRESET_NAME,
    PRESETS,
    get_preset,
)


class TestModelPreset:
    """Tests for ModelPreset dataclass."""

    def test_default_preset_exists(self):
        assert DEFAULT_PRESET_NAME in PRESETS

    def test_preset_fields(self):
        preset = PRESETS[DEFAULT_PRESET_NAME]
        assert isinstance(preset, ModelPreset)
        assert preset.name == DEFAULT_PRESET_NAME
        assert preset.url.startswith("https://")
        assert preset.filename.endswith(".gguf")


class TestGetPreset:
    """Tests for get_preset."""

    def test_valid_preset(self):
        preset = get_preset(DEFAULT_PRESET_NAME)
        assert preset.name == DEFAULT_PRESET_NAME

    def test_unknown_preset_raises(self):
        with pytest.raises(ValueError, match="Unknown embedded model preset"):
            get_preset("nonexistent-model")
