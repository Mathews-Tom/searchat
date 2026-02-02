from __future__ import annotations

import shutil
import subprocess

from searchat.config import PathResolver


class NotificationError(RuntimeError):
    """Raised when desktop notifications fail or are unavailable."""


def send_notification(*, title: str, message: str, backend: str = "auto") -> None:
    platform = PathResolver.detect_platform()
    resolved = backend.lower().strip()
    if resolved == "auto":
        if platform == "macos":
            resolved = "macos"
        elif platform == "linux":
            resolved = "linux"
        else:
            raise NotificationError(f"Unsupported platform for notifications: {platform}")

    if resolved == "macos":
        _notify_macos(title=title, message=message)
        return
    if resolved == "linux":
        _notify_linux(title=title, message=message)
        return

    raise NotificationError(f"Unsupported notifications backend: {backend}")


def _notify_macos(*, title: str, message: str) -> None:
    if shutil.which("osascript") is None:
        raise NotificationError("osascript not found; cannot send macOS notifications")

    script = f'display notification {message!r} with title {title!r}'
    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        raise NotificationError(exc.stderr.decode("utf-8", errors="replace").strip() or str(exc)) from exc


def _notify_linux(*, title: str, message: str) -> None:
    if shutil.which("notify-send") is None:
        raise NotificationError("notify-send not found; cannot send Linux notifications")

    try:
        subprocess.run(["notify-send", title, message], check=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        raise NotificationError(exc.stderr.decode("utf-8", errors="replace").strip() or str(exc)) from exc
