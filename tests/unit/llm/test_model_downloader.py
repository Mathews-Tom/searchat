from __future__ import annotations

import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from searchat.llm.model_downloader import DownloadInProgressError, acquire_lock, download_file, release_lock


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return


def _serve_directory(directory: Path) -> tuple[ThreadingHTTPServer, str]:
    handler = lambda *a, **k: _QuietHandler(*a, directory=str(directory), **k)  # type: ignore[misc]
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    host, port = server.server_address
    url_base = f"http://{host}:{port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, url_base


def test_download_file_writes_atomically(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "file.bin").write_bytes(b"hello world")

    server, base = _serve_directory(src_dir)
    try:
        dest = tmp_path / "out" / "file.bin"
        download_file(url=f"{base}/file.bin", dest_path=dest, timeout_seconds=5.0)

        assert dest.exists()
        assert dest.read_bytes() == b"hello world"
        assert not dest.with_suffix(dest.suffix + ".part").exists()
    finally:
        server.shutdown()
        server.server_close()


def test_lock_prevents_concurrent_download(tmp_path: Path) -> None:
    dest = tmp_path / "x.gguf"
    lock = dest.with_suffix(dest.suffix + ".lock")

    fd = acquire_lock(lock)
    try:
        with pytest.raises(DownloadInProgressError):
            _fd2 = acquire_lock(lock)
    finally:
        release_lock(fd, lock)
