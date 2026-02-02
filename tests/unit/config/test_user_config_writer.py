from __future__ import annotations

from pathlib import Path

import pytest
import tomli

from searchat.config.user_config_writer import (
    ConfigUpdateError,
    ensure_user_settings_exists,
    update_llm_settings,
    user_config_path,
)


def test_ensure_user_settings_exists_copies_default(tmp_path: Path) -> None:
    data_dir = tmp_path / "searchat"
    cfg = ensure_user_settings_exists(data_dir=data_dir)
    assert cfg.exists()
    assert cfg == user_config_path(data_dir=data_dir)

    content = cfg.read_text(encoding="utf-8")
    assert "[llm]" in content


def test_update_llm_settings_replaces_and_inserts(tmp_path: Path) -> None:
    data_dir = tmp_path / "searchat"
    cfg = ensure_user_settings_exists(data_dir=data_dir)

    update_llm_settings(
        config_path=cfg,
        updates={
            "embedded_model_path": "/tmp/model.gguf",
            "embedded_auto_download": False,
            "default_provider": "embedded",
        },
    )

    content = cfg.read_text(encoding="utf-8")
    tomli.loads(content)
    assert 'embedded_model_path = "/tmp/model.gguf"' in content
    assert "embedded_auto_download = false" in content
    assert 'default_provider = "embedded"' in content


def test_update_llm_settings_does_not_corrupt_header_newline(tmp_path: Path) -> None:
    cfg = tmp_path / "settings.toml"
    cfg.write_text("[llm]\nopenai_model = 'x'\n", encoding="utf-8")

    update_llm_settings(config_path=cfg, updates={"default_provider": "embedded"})

    content = cfg.read_text(encoding="utf-8")
    assert "[llm]\n" in content
    assert "[llm]default_provider" not in content
    tomli.loads(content)


def test_update_llm_settings_rejects_multiple_sections(tmp_path: Path) -> None:
    cfg = tmp_path / "settings.toml"
    cfg.write_text(
        "[llm]\nopenai_model = 'x'\n\n[llm]\nollama_model = 'y'\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigUpdateError):
        update_llm_settings(config_path=cfg, updates={"embedded_model_path": "/x"})
