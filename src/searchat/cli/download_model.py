from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from searchat.config.constants import DEFAULT_DATA_DIR
from searchat.config.user_config_writer import ensure_user_settings_exists, update_llm_settings
from searchat.llm.model_downloader import DownloadInProgressError, DownloadFailedError, download_file
from searchat.llm.model_presets import DEFAULT_PRESET_NAME, get_preset


def run_download_model(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="searchat download-model")
    parser.add_argument("--preset", default=DEFAULT_PRESET_NAME, help="Preset name to download")
    parser.add_argument("--url", default=None, help="Custom GGUF URL")
    parser.add_argument("--filename", default=None, help="Custom filename (required with --url)")
    parser.add_argument("--activate", action="store_true", help="Set llm.default_provider=embedded")
    parser.add_argument("--force", action="store_true", help="Re-download even if file exists")
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Base data dir (default: ~/.searchat). Affects config + model destination.",
    )

    args = parser.parse_args(argv)

    if args.url is not None and args.filename is None:
        raise SystemExit("--filename is required when using --url")
    if args.url is None and args.filename is not None:
        raise SystemExit("--url is required when using --filename")

    data_dir = Path(args.data_dir).expanduser() if args.data_dir else DEFAULT_DATA_DIR

    if args.url is None:
        preset = get_preset(args.preset)
        url = preset.url
        filename = preset.filename
        preset_name = preset.name
    else:
        url = args.url
        filename = args.filename
        preset_name = "custom"

    models_dir = data_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    dest_path = (models_dir / filename).resolve()
    if dest_path.exists() and not args.force:
        downloaded = False
    else:
        downloaded = True
        try:
            _download_with_progress(url=url, dest_path=dest_path)
        except DownloadInProgressError as exc:
            raise SystemExit(str(exc)) from exc
        except DownloadFailedError as exc:
            raise SystemExit(str(exc)) from exc

    cfg_path = ensure_user_settings_exists(data_dir=data_dir)

    updates: dict[str, str | int | bool] = {
        "embedded_model_path": str(dest_path),
        "embedded_default_preset": preset_name,
        "embedded_auto_download": True,
    }
    if args.activate:
        updates["default_provider"] = "embedded"

    update_llm_settings(config_path=cfg_path, updates=updates)

    if downloaded:
        print(f"Downloaded model: {dest_path}")
    else:
        print(f"Model already present: {dest_path}")
    print(f"Updated config: {cfg_path}")
    if not args.activate:
        print('To activate, set [llm].default_provider = "embedded"')

    return 0


class _ProgressPrinter:
    def __init__(self, *, label: str) -> None:
        self._label = label
        self._isatty = bool(getattr(sys.stderr, "isatty", lambda: False)())
        self._last_update = 0.0
        self._last_percent = -1
        self._prev_len = 0
        self._enabled = self._isatty

    def __call__(self, downloaded: int, total: int | None) -> None:
        if not self._enabled:
            return

        now = time.monotonic()
        if now - self._last_update < 0.2:
            return

        mb_done = downloaded / (1024 * 1024)
        if total is None or total <= 0:
            line = f"{self._label}: {mb_done:.0f} MB"
            self._write(line)
            self._last_update = now
            return

        percent = int((downloaded / total) * 100)
        if percent == self._last_percent and now - self._last_update < 0.5:
            return
        self._last_percent = percent
        self._last_update = now

        mb_total = total / (1024 * 1024)
        line = f"{self._label}: {mb_done:.0f}/{mb_total:.0f} MB ({percent}%)"
        self._write(line)

    def close(self) -> None:
        if not self._enabled:
            return
        self._write("")
        sys.stderr.write("\n")
        sys.stderr.flush()
        self._enabled = False

    def _write(self, line: str) -> None:
        # Overwrite the current line in-place.
        pad = " " * max(0, self._prev_len - len(line))
        sys.stderr.write("\r" + line + pad)
        sys.stderr.flush()
        self._prev_len = len(line)


def _download_with_progress(*, url: str, dest_path: Path) -> None:
    printer = _ProgressPrinter(label=f"Downloading {dest_path.name}")
    try:
        download_file(url=url, dest_path=dest_path, progress_cb=printer)
    finally:
        printer.close()
