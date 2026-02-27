"""FastAPI application initialization and configuration."""
from __future__ import annotations

import asyncio
import hashlib
import mimetypes
import os
import re
import time
import warnings
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from searchat.config import Config
from searchat.core.watcher import ConversationWatcher
from searchat.core.logging_config import setup_logging, get_logger
from searchat.core.progress import LoggingProgressAdapter
from searchat.api.dependencies import (
    initialize_services,
    start_background_warmup,
    get_config,
    get_indexer,
    get_watcher,
    set_watcher,
    watcher_stats,
    indexing_state,
)
import searchat.api.dependencies as deps
from searchat.api.readiness import get_readiness
from searchat.api.routers import (
    search_router,
    conversations_router,
    bookmarks_router,
    stats_router,
    indexing_router,
    backup_router,
    admin_router,
    status_router,
    chat_router,
    queries_router,
    code_router,
    docs_router,
    patterns_router,
    dashboards_router,
)
from searchat.config.constants import (
    APP_VERSION,
    DEFAULT_HOST,
    DEFAULT_PORT,
    PORT_SCAN_RANGE,
    ENV_PORT,
    ENV_HOST,
    ERROR_INVALID_PORT,
    ERROR_PORT_IN_USE,
)

warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module=r"multiprocessing\.resource_tracker",
)

_warn_filter = "ignore::UserWarning:multiprocessing.resource_tracker"
_existing_warn = os.environ.get("PYTHONWARNINGS", "")
if _warn_filter not in _existing_warn:
    os.environ["PYTHONWARNINGS"] = (
        f"{_existing_warn},{_warn_filter}" if _existing_warn else _warn_filter
)

# Ensure correct JS MIME types across platforms (notably Windows).
# Without this, browsers may refuse to load ES modules from /static.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/javascript", ".mjs")


# ---------------------------------------------------------------------------
# Static-asset cache busting
# ---------------------------------------------------------------------------
_WEB_DIR = Path(__file__).parent.parent / "web"
_HTML_PATH = _WEB_DIR / "index.html"
_STATIC_DIR = _WEB_DIR / "static"

_CACHE_BUST_RE = re.compile(
    r"(?P<attr>\b(?:src|href))=(?P<q>['\"])(?P<path>/static/[^'\"]+)(?P=q)"
)


def _static_fingerprint() -> str:
    """Hash the combined mtime of every file under web/static/.

    Changes on any JS/CSS/asset edit, no version bump needed.
    """
    h = hashlib.md5(usedforsecurity=False)
    for p in sorted(_STATIC_DIR.rglob("*")):
        if p.is_file():
            h.update(f"{p.relative_to(_STATIC_DIR)}:{p.stat().st_mtime_ns}".encode())
    return h.hexdigest()[:10]


def _cache_bust_static_assets(html: str, fingerprint: str) -> str:
    """Append a fingerprint query param to local /static asset URLs."""

    def repl(match: re.Match[str]) -> str:
        attr, quote, path = match.group("attr"), match.group("q"), match.group("path")
        base, sep, fragment = path.partition("#")
        if "?" in base:
            return match.group(0)
        busted = f"{base}?v={fingerprint}"
        if sep:
            busted = f"{busted}#{fragment}"
        return f"{attr}={quote}{busted}{quote}"

    return _CACHE_BUST_RE.sub(repl, html)


def _build_html_cache() -> tuple[str, str]:
    """Read and cache-bust both HTML pages using the current static fingerprint."""
    fp = _static_fingerprint()
    index = _cache_bust_static_assets(_HTML_PATH.read_text(encoding="utf-8"), fp)
    chat_path = _WEB_DIR / "chat.html"
    chat = _cache_bust_static_assets(chat_path.read_text(encoding="utf-8"), fp) if chat_path.exists() else ""
    return index, chat


_CACHED_HTML, _CACHED_CHAT_HTML = _build_html_cache()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Manage startup and shutdown lifecycle."""
    # --- startup ---
    started = time.perf_counter()
    initialize_services()
    start_background_warmup()

    config = get_config()
    setup_logging(config.logging)
    _logger = get_logger(__name__)

    if os.getenv("SEARCHAT_PROFILE_STARTUP") == "1":
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        _logger.info("Startup: initialize_services + schedule warmup %.1fms", elapsed_ms)

    asyncio.create_task(_start_watcher_background(config))

    if os.getenv("SEARCHAT_PROFILE_STARTUP") == "1":
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        _logger.info("Startup: total startup_event %.1fms", elapsed_ms)

    yield

    # --- shutdown ---
    watcher = get_watcher()
    if watcher:
        watcher.stop()
        set_watcher(None)


# Create FastAPI app
app = FastAPI(
    title="Searchat API",
    description="Local search for your AI coding conversations",
    version=APP_VERSION,
    lifespan=lifespan,
)

# CORS middleware — origins from config, defaults to localhost-only
_cors_origins = Config.load().server.cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# No-cache middleware for static assets (prevents stale JS/CSS during dev)
# ---------------------------------------------------------------------------
class NoCacheStaticMiddleware(BaseHTTPMiddleware):
    """Force browsers to revalidate /static assets on every request."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        response: Response = await call_next(request)
        if request.url.path.startswith("/static"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


app.add_middleware(NoCacheStaticMiddleware)

# Mount static files
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# Mount docs directory for infographics
docs_path = Path(__file__).parent.parent.parent.parent / "docs"
if docs_path.exists():
    app.mount("/docs", StaticFiles(directory=str(docs_path)), name="docs")

# Register routers
app.include_router(search_router, prefix="/api", tags=["search"])
app.include_router(conversations_router, prefix="/api", tags=["conversations"])
app.include_router(bookmarks_router, prefix="/api", tags=["bookmarks"])
app.include_router(stats_router, prefix="/api", tags=["statistics"])
app.include_router(indexing_router, prefix="/api", tags=["indexing"])
app.include_router(backup_router, prefix="/api/backup", tags=["backup"])
app.include_router(admin_router, prefix="/api", tags=["admin"])
app.include_router(status_router, prefix="/api", tags=["status"])
app.include_router(chat_router, prefix="/api", tags=["chat"])
app.include_router(queries_router, prefix="/api", tags=["queries"])
app.include_router(code_router, prefix="/api", tags=["code"])
app.include_router(docs_router, prefix="/api", tags=["docs"])
app.include_router(patterns_router, prefix="/api", tags=["patterns"])
app.include_router(dashboards_router, prefix="/api", tags=["dashboards"])


def on_new_conversations(file_paths: list[str]) -> None:
    """Callback when watcher detects new conversation files."""
    global projects_cache, watcher_stats, indexing_state

    logger = get_logger(__name__)
    logger.info(f"Auto-indexing {len(file_paths)} new conversations")

    try:
        indexer = get_indexer()
        deps.get_or_create_search_engine()  # ensure engine exists before indexing

        # Mark indexing in progress
        indexing_state["in_progress"] = True
        indexing_state["operation"] = "watcher"
        indexing_state["started_at"] = datetime.now().isoformat()
        indexing_state["files_total"] = len(file_paths)
        indexing_state["files_processed"] = 0

        # Use logging-based progress for background task
        progress = LoggingProgressAdapter()

        enable_adaptive = False
        try:
            enable_adaptive = bool(
                getattr(indexer, "config", None)
                and getattr(indexer.config, "indexing", None)
                and indexer.config.indexing.enable_adaptive_indexing
            )
        except Exception:
            enable_adaptive = False

        if enable_adaptive and hasattr(indexer, "index_adaptive"):
            stats = indexer.index_adaptive(file_paths, progress)
        else:
            stats = indexer.index_append_only(file_paths, progress)

        updated_conversations = getattr(stats, "updated_conversations", 0)
        if stats.new_conversations > 0 or updated_conversations > 0:
            deps.invalidate_search_index()

            watcher_stats["indexed_count"] += stats.new_conversations + updated_conversations
            watcher_stats["last_update"] = datetime.now().isoformat()

            logger.info(
                f"Indexed {stats.new_conversations} new conversations and "
                f"updated {updated_conversations} conversations "
                f"in {stats.update_time_seconds:.2f}s"
            )
    except Exception as e:
        logger.error(f"Failed to index new conversations: {e}")
    finally:
        # Mark indexing complete
        indexing_state["in_progress"] = False
        indexing_state["operation"] = None



async def _start_watcher_background(config):
    readiness = get_readiness()
    readiness.set_watcher("starting")

    logger = get_logger(__name__)
    try:
        indexer = get_indexer()
        watcher = ConversationWatcher(
            config=config,
            on_update=on_new_conversations,
            batch_delay_seconds=5.0,
            debounce_seconds=2.0,
        )

        indexed_paths = await asyncio.to_thread(indexer.get_indexed_file_paths)
        watcher.set_indexed_files(indexed_paths)

        watcher.start()
        set_watcher(watcher)

        readiness.set_watcher("running")
        logger.info(
            f"Live watcher started, monitoring {len(watcher.get_watched_directories())} directories"
        )
    except Exception as e:
        readiness.set_watcher("error", error=str(e))
        logger.error(f"Failed to start watcher: {e}")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page."""
    return HTMLResponse(_CACHED_HTML)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon_ico():
    """Redirect default browser favicon request to our SVG favicon."""
    return RedirectResponse(url="/static/favicon.svg")


@app.get("/conversation/{conversation_id}", response_class=HTMLResponse)
async def serve_conversation_page(conversation_id: str):
    """Serve HTML page for viewing a specific conversation."""
    # For now, serve the same main page (it handles conversation viewing via client-side routing)
    return HTMLResponse(_CACHED_HTML)


@app.get("/chat", response_class=HTMLResponse)
async def serve_chat_page():
    """Serve the standalone Chat with History page."""
    return HTMLResponse(_CACHED_CHAT_HTML)


def main():
    """Run the server with configurable host and port."""
    import uvicorn
    import socket
    import warnings
    import threading
    import time
    import webbrowser
    import sys

    prog = Path(sys.argv[0]).name
    argv = set(sys.argv[1:])
    if prog.startswith("searchat-web"):
        if "--version" in argv:
            from searchat import __version__

            print(__version__)
            return
        if "-h" in argv or "--help" in argv:
            print("Usage: searchat-web")
            print()
            print("Environment variables:")
            print(f"  {ENV_HOST}=<host>   (default: {DEFAULT_HOST})")
            print(f"  {ENV_PORT}=<port>   (default: auto-scan {PORT_SCAN_RANGE[0]}-{PORT_SCAN_RANGE[1]})")
            print("  SEARCHAT_OPEN_BROWSER=0   Disable opening the browser tab")
            print()
            return

    # Python 3.12 can emit a noisy multiprocessing.resource_tracker warning on
    # shutdown with some native deps (e.g., torch/sentence-transformers).
    warnings.filterwarnings(
        "ignore",
        message=r"resource_tracker: There appear to be .* leaked semaphore objects to clean up at shutdown",
        category=UserWarning,
    )

    # Get host from environment or use default
    host = os.getenv(ENV_HOST, DEFAULT_HOST)

    # Get port from environment or scan for available port
    env_port = os.getenv(ENV_PORT)
    if env_port:
        try:
            port = int(env_port)
            if not (1 <= port <= 65535):
                print(ERROR_INVALID_PORT.format(port=port))
                return
        except ValueError:
            print(ERROR_INVALID_PORT.format(port=env_port))
            return
    else:
        # Scan for available port in range
        port, max_port = PORT_SCAN_RANGE

        while port <= max_port:
            try:
                # Test if port is available
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind((host, port))
                # Port is available
                break
            except OSError:
                port += 1

        if port > max_port:
            print(ERROR_PORT_IN_USE.format(
                start=PORT_SCAN_RANGE[0],
                end=PORT_SCAN_RANGE[1],
                port=port
            ))
            return

    print(f"Starting Searchat server...")
    print(f"  URL: http://localhost:{port}")
    print(f"  Host: {host}")
    print(f"  Port: {port}")
    print()
    print("Press Ctrl+C to stop")

    open_browser_raw = os.getenv("SEARCHAT_OPEN_BROWSER", "1").strip().lower()
    open_browser = open_browser_raw not in {"0", "false", "no", "off"}
    if "--no-browser" in argv:
        open_browser = False
    interactive = sys.stdout.isatty()

    def _open_browser_when_ready() -> None:
        url_host = host
        if host in {"0.0.0.0", "::", ""}:
            url_host = "localhost"
        url = f"http://{url_host}:{port}"

        probe_host = "127.0.0.1" if url_host == "localhost" else url_host

        deadline = time.time() + 10.0
        while time.time() < deadline:
            try:
                with socket.create_connection((probe_host, port), timeout=0.25):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            print(f"Warning: server did not start within 10s; not opening browser ({url})")
            return

        try:
            webbrowser.open_new_tab(url)
        except Exception as exc:
            print(f"Warning: failed to open browser tab: {exc}")

    if open_browser and interactive:
        threading.Thread(target=_open_browser_when_ready, daemon=True).start()

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
