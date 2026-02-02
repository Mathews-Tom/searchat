from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path
from urllib.request import Request, urlopen


class DownloadInProgressError(RuntimeError):
    """Raised when another process is already downloading the same file."""


class DownloadFailedError(RuntimeError):
    """Raised when a download fails or cannot be completed."""


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def acquire_lock(lock_path: Path) -> int:
    """Acquire an exclusive lock via O_EXCL lock file.

    Returns:
        OS file descriptor for the lock.

    Raises:
        DownloadInProgressError: If lock already exists.
    """
    ensure_directory(lock_path.parent)
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError as exc:
        raise DownloadInProgressError(f"Download lock exists: {lock_path}") from exc

    payload = f"pid={os.getpid()} started_at={time.time():.3f}\n"
    os.write(fd, payload.encode("ascii", errors="strict"))
    os.fsync(fd)
    return fd


def release_lock(fd: int, lock_path: Path) -> None:
    try:
        os.close(fd)
    finally:
        try:
            lock_path.unlink(missing_ok=True)
        except Exception:
            # Best effort cleanup; caller should still treat download as done.
            pass


def download_file(
    *,
    url: str,
    dest_path: Path,
    timeout_seconds: float = 60.0,
    progress_cb: Callable[[int, int | None], None] | None = None,
) -> None:
    """Download a file with atomic finalize.

    Downloads to a temporary .part file and atomically replaces dest_path on success.

    Args:
        url: Remote URL.
        dest_path: Destination file path.
        timeout_seconds: Network timeout (connect/read).
        progress_cb: Optional callback receiving (downloaded_bytes, total_bytes_or_None).

    Raises:
        DownloadFailedError: On any download failure.
    """
    ensure_directory(dest_path.parent)

    part_path = dest_path.with_suffix(dest_path.suffix + ".part")
    lock_path = dest_path.with_suffix(dest_path.suffix + ".lock")
    fd = acquire_lock(lock_path)

    try:
        req = Request(url, headers={"User-Agent": "searchat"})
        with urlopen(req, timeout=timeout_seconds) as resp:
            total: int | None
            length = resp.headers.get("Content-Length")
            if length is None:
                total = None
            else:
                try:
                    total = int(length)
                except ValueError:
                    total = None

            downloaded = 0
            try:
                with open(part_path, "wb") as f:
                    while True:
                        chunk = resp.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_cb is not None:
                            progress_cb(downloaded, total)
                    f.flush()
                    os.fsync(f.fileno())
            except Exception as exc:
                raise DownloadFailedError(f"Failed while writing {part_path}: {exc}") from exc

        os.replace(part_path, dest_path)
    except DownloadInProgressError:
        raise
    except Exception as exc:
        raise DownloadFailedError(f"Failed to download {url}: {exc}") from exc
    finally:
        try:
            part_path.unlink(missing_ok=True)
        except Exception:
            pass
        release_lock(fd, lock_path)
