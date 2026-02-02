from __future__ import annotations

import re
import shutil
from pathlib import Path

import tomli

from searchat.config.constants import (
    DEFAULT_CONFIG_SUBDIR,
    DEFAULT_DATA_DIR,
    DEFAULT_SETTINGS_FILE,
    SETTINGS_FILE,
)


class ConfigUpdateError(RuntimeError):
    """Raised when user config cannot be updated safely."""


def user_config_path(*, data_dir: Path | None = None) -> Path:
    base = data_dir or DEFAULT_DATA_DIR
    return base / DEFAULT_CONFIG_SUBDIR / SETTINGS_FILE


def ensure_user_settings_exists(*, data_dir: Path | None = None) -> Path:
    """Ensure the user settings.toml exists; create by copying defaults if missing."""
    cfg_path = user_config_path(data_dir=data_dir)
    cfg_path.parent.mkdir(parents=True, exist_ok=True)

    if cfg_path.exists():
        return cfg_path

    default_config = Path(__file__).parent / DEFAULT_SETTINGS_FILE
    if not default_config.exists():
        raise ConfigUpdateError(f"Default config not found: {default_config}")

    shutil.copy(default_config, cfg_path)
    return cfg_path


def update_llm_settings(*, config_path: Path, updates: dict[str, str | int | bool]) -> None:
    """Update [llm] keys in a TOML file without rewriting unrelated sections.

    This is a minimal text patcher: it only edits/replaces key lines in the [llm]
    section, preserving other content.

    Raises:
        ConfigUpdateError: If multiple [llm] sections exist or file is malformed.
    """
    content = config_path.read_text(encoding="utf-8")

    llm_header_re = re.compile(r"(?m)^\[llm\]\s*$")
    headers = list(llm_header_re.finditer(content))
    if len(headers) > 1:
        raise ConfigUpdateError("Multiple [llm] sections found; refusing to update.")

    if not headers:
        # Append new section.
        if not content.endswith("\n"):
            content += "\n"
        content += "\n[llm]\n"
        section_start = len(content)
        section_end = len(content)
    else:
        section_start = headers[0].end()
        # Keep section content strictly after the header line. Handle both \n
        # and \r\n line endings.
        while section_start < len(content) and content[section_start] in ("\r", "\n"):
            section_start += 1
        next_header = re.search(r"(?m)^\[[^\]]+\]\s*$", content[section_start:])
        if next_header is None:
            section_end = len(content)
        else:
            section_end = section_start + next_header.start()

    before = content[:section_start]
    section = content[section_start:section_end]
    after = content[section_end:]

    # Replace existing keys.
    for key, value in updates.items():
        line = _format_toml_kv(key, value)
        key_re = re.compile(rf"(?m)^(\s*{re.escape(key)}\s*=\s*).*$")
        if key_re.search(section):
            section = key_re.sub(line, section)
        else:
            # Insert near the start of the section (after initial blank lines/comments).
            insert_at = 0
            for m in re.finditer(r"(?m)^(?:\s*$|\s*#.*$)", section):
                if m.start() == insert_at:
                    insert_at = m.end() + 1
                    continue
                break
            if insert_at < 0 or insert_at > len(section):
                insert_at = 0
            if section and not section.startswith("\n") and insert_at == 0:
                section = "\n" + section
                insert_at = 1
            section = section[:insert_at] + line + "\n" + section[insert_at:]

    updated = before + section + after

    # Validate before writing to disk.
    try:
        tomli.loads(updated)
    except tomli.TOMLDecodeError as exc:
        raise ConfigUpdateError(f"Refusing to write invalid settings.toml: {exc}") from exc

    tmp_path = config_path.with_suffix(config_path.suffix + ".tmp")
    tmp_path.write_text(updated, encoding="utf-8")
    tmp_path.replace(config_path)


def _format_toml_kv(key: str, value: str | int | bool) -> str:
    if isinstance(value, bool):
        rendered = "true" if value else "false"
    elif isinstance(value, int):
        rendered = str(value)
    else:
        rendered = _toml_quote(value)
    return f"{key} = {rendered}"


def _toml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
