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


def test_ensure_user_settings_raises_when_default_missing(tmp_path: Path, monkeypatch) -> None:
    """When default settings file does not exist, ConfigUpdateError is raised."""
    from searchat.config.user_config_writer import ConfigUpdateError
    import searchat.config.user_config_writer as ucw

    # Point DEFAULT_SETTINGS_FILE to a nonexistent name
    monkeypatch.setattr(ucw, "DEFAULT_SETTINGS_FILE", "nonexistent_default.toml")
    data_dir = tmp_path / "fresh"
    with pytest.raises(ConfigUpdateError, match="Default config not found"):
        ensure_user_settings_exists(data_dir=data_dir)


def test_ensure_user_settings_returns_existing(tmp_path: Path) -> None:
    """Second call returns existing file without re-copying."""
    data_dir = tmp_path / "data"
    path1 = ensure_user_settings_exists(data_dir=data_dir)
    path2 = ensure_user_settings_exists(data_dir=data_dir)
    assert path1 == path2


def test_update_appends_llm_section_when_missing(tmp_path: Path) -> None:
    cfg = tmp_path / "settings.toml"
    cfg.write_text('[search]\nmode = "hybrid"\n', encoding="utf-8")
    update_llm_settings(config_path=cfg, updates={"model": "gpt-4.1"})
    content = cfg.read_text(encoding="utf-8")
    assert "[llm]" in content
    assert 'model = "gpt-4.1"' in content
    tomli.loads(content)


def test_update_appends_to_file_without_trailing_newline(tmp_path: Path) -> None:
    cfg = tmp_path / "settings.toml"
    cfg.write_text('[search]\nmode = "hybrid"', encoding="utf-8")  # no trailing \n
    update_llm_settings(config_path=cfg, updates={"enabled": True})
    content = cfg.read_text(encoding="utf-8")
    assert "[llm]" in content
    assert "enabled = true" in content
    tomli.loads(content)


def test_update_bool_and_int_values(tmp_path: Path) -> None:
    cfg = tmp_path / "settings.toml"
    cfg.write_text('[llm]\nmodel = "x"\n', encoding="utf-8")
    update_llm_settings(
        config_path=cfg,
        updates={"enabled": False, "max_tokens": 4096},
    )
    content = cfg.read_text(encoding="utf-8")
    assert "enabled = false" in content
    assert "max_tokens = 4096" in content
    tomli.loads(content)
