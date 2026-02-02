from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from pathlib import Path

from searchat.config import Config, PathResolver
from searchat.core.connectors import get_connectors
from searchat.core.search_engine import SearchEngine
from searchat.models import SearchFilters, SearchMode

from searchat.daemon.notify import NotificationError, send_notification


@dataclass(frozen=True)
class GhostSuggestion:
    query: str
    conversation_id: str
    title: str
    score: float


def main() -> None:
    parser = argparse.ArgumentParser(prog="searchat-ghost")
    parser.add_argument("--once", action="store_true", help="Run a single scan and exit")
    parser.add_argument("--no-notify", action="store_true", help="Disable desktop notifications")
    args = parser.parse_args()

    config = Config.load()
    if not config.daemon.enabled and not args.once:
        raise SystemExit(
            "Ghost daemon is disabled. Enable [daemon].enabled=true in ~/.searchat/config/settings.toml or run with --once."
        )

    search_dir = PathResolver.get_shared_search_dir(config)
    engine = SearchEngine(search_dir, config)

    daemon = GhostDaemon(
        config=config,
        engine=engine,
        notifications_enabled=(config.daemon.notifications_enabled and not args.no_notify),
    )

    if args.once:
        daemon.scan_once()
        return

    daemon.run_forever()


class GhostDaemon:
    def __init__(
        self,
        *,
        config: Config,
        engine: SearchEngine,
        notifications_enabled: bool,
    ) -> None:
        self._config = config
        self._engine = engine
        self._notifications_enabled = notifications_enabled
        self._file_state: dict[str, float] = {}
        self._last_rescan = 0.0

    def run_forever(self) -> None:
        while True:
            self.scan_once()
            time.sleep(max(1, int(self._config.daemon.poll_seconds)))

    def scan_once(self) -> None:
        now = time.time()
        if now - self._last_rescan >= max(1, int(self._config.daemon.rescan_seconds)):
            self._refresh_file_list()
            self._last_rescan = now

        candidates = sorted(self._file_state.items(), key=lambda kv: kv[1], reverse=True)[:50]
        for file_path, last_seen_mtime in candidates:
            path = Path(file_path)
            if not path.exists():
                continue
            mtime = path.stat().st_mtime
            if mtime <= last_seen_mtime:
                continue

            text = path.read_text(encoding="utf-8")
            signatures = extract_signatures(text)
            self._file_state[file_path] = mtime

            for signature in signatures:
                if len(signature) < int(self._config.daemon.min_query_length):
                    continue
                suggestions = self._search(signature)
                if not suggestions:
                    continue
                self._emit(signature, suggestions)

    def _refresh_file_list(self) -> None:
        files: list[Path] = []
        for connector in get_connectors():
            try:
                files.extend(connector.discover_files(self._config))
            except Exception as exc:
                raise RuntimeError(f"Failed to discover files for connector {getattr(connector, 'name', '<unknown>')}: {exc}") from exc

        for path in files:
            key = str(path)
            if key not in self._file_state:
                self._file_state[key] = 0.0

    def _search(self, query: str) -> list[GhostSuggestion]:
        # Use keyword mode to avoid requiring semantic warmup.
        results = self._engine.search(query, mode=SearchMode.KEYWORD, filters=SearchFilters())
        suggestions: list[GhostSuggestion] = []
        for r in results.results[: int(self._config.daemon.max_suggestions)]:
            suggestions.append(
                GhostSuggestion(
                    query=query,
                    conversation_id=r.conversation_id,
                    title=r.title,
                    score=r.score,
                )
            )
        return suggestions

    def _emit(self, query: str, suggestions: list[GhostSuggestion]) -> None:
        title = "Searchat Ghost"
        top = suggestions[0]
        message = f"Found related history for: {query}\nTop hit: {top.title} ({top.conversation_id})"

        if self._notifications_enabled:
            try:
                send_notification(
                    title=title,
                    message=message,
                    backend=self._config.daemon.notifications_backend,
                )
            except NotificationError as exc:
                raise RuntimeError(str(exc)) from exc
        else:
            print(message)


_ERROR_PATTERNS: list[tuple[str, str]] = [
    (r"(?m)^Traceback \(most recent call last\):$", "traceback"),
    (r"(?m)^\w*Error: .+$", "error"),
    (r"(?m)^\w*Exception: .+$", "exception"),
    (r"(?m)^panic: .+$", "panic"),
    (r"(?m)^FAILED .*?$", "failed"),
]


def extract_signatures(text: str) -> list[str]:
    signatures: list[str] = []

    for pattern, _kind in _ERROR_PATTERNS:
        import re

        if re.search(pattern, text):
            tail = _tail(text, 40)
            signatures.append(tail)

    # Deduplicate preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for sig in signatures:
        if sig in seen:
            continue
        seen.add(sig)
        unique.append(sig)
    return unique


def _tail(text: str, lines: int) -> str:
    parts = text.splitlines()[-lines:]
    return "\n".join(parts).strip()
