"""FastAPI application initialization and configuration."""
from __future__ import annotations

import asyncio
import mimetypes
import os
import time
import warnings
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime
from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

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
    get_config,
    get_indexer,
    get_watcher,
    set_watcher,
)
import searchat.api.dependencies as deps
from searchat.api import state as api_state
from searchat.api.readiness import get_readiness
from searchat.api.warmup import invalidate_search_index, start_background_warmup
from searchat.api.templates import templates
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
    expertise_router,
    knowledge_graph_router,
    fragments_router,
    health_router,
    palace_router,
    disk_router,
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
# Static-asset paths
# ---------------------------------------------------------------------------
_WEB_DIR = Path(__file__).parent.parent / "web"
_STATIC_DIR = _WEB_DIR / "static"


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
# Reject cross-origin state-changing requests (drive-by CSRF)
# ---------------------------------------------------------------------------
class RejectCrossOriginMutationsMiddleware(BaseHTTPMiddleware):
    """Reject a state-changing request whose browser-sent Origin header
    is neither same-origin nor in the configured CORS allowlist.

    CORSMiddleware alone does not stop this class of request: it only
    withholds `Access-Control-Allow-Origin` from the *response*, which
    blocks a cross-origin script from *reading* the result but does
    nothing to stop the request from being sent and executed -- a
    "simple" cross-origin POST (a bare `<form method=POST>`, no custom
    Content-Type) never triggers a CORS preflight at all. Any website
    the user's browser visits can silently auto-submit such a form to
    this locally-bound server and trigger a real state change (e.g.
    `POST /api/backup/restore`, which overwrites the live index with an
    old backup, or `POST /api/shutdown`) with no user interaction and no
    need to read the response.

    A request whose Origin's host:port matches the request's own Host
    header is always same-origin and is allowed regardless of the
    static allowlist -- main()'s own port auto-scanner (PORT_SCAN_RANGE,
    8000-8010) silently picks a non-default port whenever 8000 is
    already taken, and SEARCHAT_HOST=0.0.0.0 deployments are reached via
    a LAN IP; a purely static `cors_origins` check would reject the
    app's own legitimate frontend under either condition. The static
    `allowed_origins` list remains the fallback for a deliberately
    configured cross-origin caller.

    A request with no Origin header (curl, Python's requests, the MCP
    stdio transport, direct socket-level HTTP -- none of them set one)
    is allowed through unchanged; only a browser-sent Origin that fails
    both checks is rejected. GET/HEAD/OPTIONS are never state-changing
    and are always allowed through unchanged.
    """

    _SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

    def __init__(self, app: FastAPI, allowed_origins: list[str]) -> None:
        super().__init__(app)
        self._allowed_origins = frozenset(allowed_origins)

    @staticmethod
    def _is_same_origin(origin: str, host_header: str) -> bool:
        try:
            origin_netloc = urlsplit(origin).netloc
        except ValueError:
            return False
        return bool(origin_netloc) and origin_netloc.lower() == host_header.lower()

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if request.method not in self._SAFE_METHODS:
            origin = request.headers.get("origin")
            if origin is not None:
                host_header = request.headers.get("host", "")
                same_origin = self._is_same_origin(origin, host_header)
                if not same_origin and origin not in self._allowed_origins:
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Cross-origin request rejected"},
                    )
        return await call_next(request)


app.add_middleware(RejectCrossOriginMutationsMiddleware, allowed_origins=_cors_origins)

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
app.include_router(expertise_router)
app.include_router(knowledge_graph_router)
app.include_router(fragments_router)
app.include_router(health_router, prefix="/api", tags=["health"])
app.include_router(palace_router)
app.include_router(disk_router, prefix="/api", tags=["disk"])


def on_new_conversations(file_paths: list[str]) -> None:
    """Callback when watcher detects new conversation files."""
    logger = get_logger(__name__)
    logger.info(f"Auto-indexing {len(file_paths)} new conversations")

    try:
        indexer = get_indexer()
        deps.get_or_create_search_engine()  # ensure engine exists before indexing

        # Mark indexing in progress
        api_state.indexing_state["in_progress"] = True
        api_state.indexing_state["operation"] = "watcher"
        api_state.indexing_state["started_at"] = datetime.now().isoformat()
        api_state.indexing_state["files_total"] = len(file_paths)
        api_state.indexing_state["files_processed"] = 0

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
            invalidate_search_index()

            api_state.watcher_stats["indexed_count"] += stats.new_conversations + updated_conversations
            api_state.watcher_stats["last_update"] = datetime.now().isoformat()

            logger.info(
                f"Indexed {stats.new_conversations} new conversations and "
                f"updated {updated_conversations} conversations "
                f"in {stats.update_time_seconds:.2f}s"
            )
    except Exception as e:
        logger.error(f"Failed to index new conversations: {e}")
    finally:
        # Mark indexing complete
        api_state.indexing_state["in_progress"] = False
        api_state.indexing_state["operation"] = None



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
async def root(request: Request):
    """Serve the main HTML page."""
    return templates.TemplateResponse(request, "index.html")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon_ico():
    """Redirect default browser favicon request to our SVG favicon."""
    return RedirectResponse(url="/static/favicon.svg")


@app.get("/conversation/{conversation_id}", response_class=HTMLResponse)
async def serve_conversation_page(request: Request, conversation_id: str):
    """Serve HTML page for viewing a specific conversation."""
    return templates.TemplateResponse(
        request, "conversation.html", {"conversation_id": conversation_id}
    )


@app.get("/chat", response_class=HTMLResponse)
async def serve_chat_page(request: Request):
    """Serve the standalone Chat with History page."""
    return templates.TemplateResponse(request, "chat.html")


@app.get("/manage", response_class=HTMLResponse)
async def serve_manage_page(request: Request):
    """Serve the conversation management page."""
    return templates.TemplateResponse(request, "manage.html")


def main(argv: list[str] | None = None, prog_name: str | None = None):
    """Run the server with configurable host and port."""
    import uvicorn
    import socket
    import warnings
    import threading
    import time
    import webbrowser
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    prog = prog_name or Path(sys.argv[0]).name
    arg_set = set(args)
    if prog.startswith("searchat-web") or prog == "searchat web":
        if "--version" in arg_set:
            from searchat import __version__

            print(__version__)
            return
        if "-h" in arg_set or "--help" in arg_set:
            print(f"Usage: {prog}")
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
    if "--no-browser" in args:
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
