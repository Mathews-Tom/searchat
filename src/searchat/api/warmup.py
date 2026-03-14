"""Warmup and invalidation orchestration for API runtime services."""

from __future__ import annotations

import asyncio
import logging
import os
import time

from searchat.api import state as api_state
from searchat.api.readiness import get_readiness

logger = logging.getLogger(__name__)


def start_background_warmup() -> None:
    """Kick off background warmup (non-blocking, idempotent)."""
    from searchat.api import dependencies as deps

    try:
        deps.get_config()
        deps.get_search_dir()
    except RuntimeError:
        return

    readiness = get_readiness()
    readiness.mark_warmup_started()

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    if api_state.warmup_task is not None and not api_state.warmup_task.done():
        return

    api_state.warmup_task = loop.create_task(_warmup_all())


async def _warmup_all() -> None:
    """Warm up heavy components in the background."""
    await asyncio.gather(
        asyncio.to_thread(_warmup_duckdb_parquet),
        asyncio.to_thread(_warmup_embedded_model),
    )

    from searchat.api import dependencies as deps

    await asyncio.to_thread(deps._ensure_search_engine)
    await asyncio.to_thread(_warmup_semantic_components)


def _warmup_embedded_model() -> None:
    """Ensure embedded GGUF model exists when embedded provider is enabled."""
    from pathlib import Path

    from searchat.api import dependencies as deps
    from searchat.config.constants import DEFAULT_DATA_DIR
    from searchat.config.user_config_writer import ensure_user_settings_exists, update_llm_settings
    from searchat.llm.model_downloader import DownloadInProgressError, download_file
    from searchat.llm.model_presets import get_preset

    readiness = get_readiness()
    try:
        config = deps.get_config()
    except RuntimeError:
        return

    if config.llm.default_provider.lower() != "embedded":
        readiness.set_component("embedded_model", "idle")
        return

    readiness.set_component("embedded_model", "loading")
    try:
        configured = config.llm.embedded_model_path
        if configured:
            configured_path = Path(configured).expanduser()
            if configured_path.exists():
                readiness.set_component("embedded_model", "ready")
                return

        if not config.llm.embedded_auto_download:
            raise RuntimeError(
                "Embedded provider enabled but embedded_model_path is not set or missing. "
                "Set [llm].embedded_model_path or run 'searchat download-model --activate'."
            )

        preset = get_preset(config.llm.embedded_default_preset)
        dest_path = (DEFAULT_DATA_DIR / "models" / preset.filename).resolve()

        if not dest_path.exists():
            readiness.set_component(
                "embedded_model",
                "loading",
                error="Downloading embedded model (first run)...",
            )

            last_update = 0.0
            last_percent = -1

            def _progress(downloaded: int, total: int | None) -> None:
                nonlocal last_update, last_percent

                now = time.monotonic()
                if total is None or total <= 0:
                    if now - last_update < 0.5:
                        return
                    last_update = now
                    mb = downloaded / (1024 * 1024)
                    readiness.set_component(
                        "embedded_model",
                        "loading",
                        error=f"Downloading embedded model: {mb:.0f} MB...",
                    )
                    return

                percent = int((downloaded / total) * 100)
                if percent == last_percent and now - last_update < 0.5:
                    return
                last_percent = percent
                last_update = now
                mb_done = downloaded / (1024 * 1024)
                mb_total = total / (1024 * 1024)
                readiness.set_component(
                    "embedded_model",
                    "loading",
                    error=f"Downloading embedded model: {mb_done:.0f}/{mb_total:.0f} MB ({percent}%)",
                )

            download_file(url=preset.url, dest_path=dest_path, progress_cb=_progress)

        cfg_path = ensure_user_settings_exists(data_dir=DEFAULT_DATA_DIR)
        update_llm_settings(
            config_path=cfg_path,
            updates={
                "embedded_model_path": str(dest_path),
                "embedded_default_preset": preset.name,
                "embedded_auto_download": True,
            },
        )

        config.llm.embedded_model_path = str(dest_path)
        readiness.set_component("embedded_model", "ready")
    except DownloadInProgressError as exc:
        readiness.set_component("embedded_model", "loading", error=str(exc))
    except Exception as exc:
        readiness.set_component("embedded_model", "error", error=str(exc))


def _warmup_duckdb_parquet() -> None:
    from searchat.api import dependencies as deps

    readiness = get_readiness()
    started = time.perf_counter()
    try:
        readiness.set_component("duckdb", "loading")
        readiness.set_component("parquet", "loading")

        store = deps.get_duckdb_store()
        store.validate_parquet_scan()

        readiness.set_component("duckdb", "ready")
        readiness.set_component("parquet", "ready")
    except Exception as exc:
        msg = str(exc)
        readiness.set_component("duckdb", "error", error=msg)
        readiness.set_component("parquet", "error", error=msg)
    finally:
        if os.getenv("SEARCHAT_PROFILE_WARMUP") == "1":
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            logger.info("Warmup: duckdb/parquet %.1fms", elapsed_ms)


def _warmup_semantic_components() -> None:
    from searchat.api import dependencies as deps

    readiness = get_readiness()
    started = time.perf_counter()
    try:
        engine = deps._ensure_search_engine()

        readiness.set_component("metadata", "loading")
        engine.ensure_metadata_ready()
        readiness.set_component("metadata", "ready")

        readiness.set_component("faiss", "loading")
        engine.ensure_faiss_loaded()
        readiness.set_component("faiss", "ready")

        readiness.set_component(
            "embedder",
            "loading",
            error="Preparing embedding model (may download on first run)...",
        )
        engine.ensure_embedder_loaded()
        readiness.set_component("embedder", "ready")
    except Exception as exc:
        msg = str(exc)
        snap = readiness.snapshot()
        if snap.components.get("metadata") != "ready":
            readiness.set_component("metadata", "error", error=msg)
        if snap.components.get("faiss") != "ready":
            readiness.set_component("faiss", "error", error=msg)
        if snap.components.get("embedder") != "ready":
            readiness.set_component("embedder", "error", error=msg)
    finally:
        if os.getenv("SEARCHAT_PROFILE_WARMUP") == "1":
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            logger.info("Warmup: semantic components %.1fms", elapsed_ms)


def invalidate_search_index() -> None:
    """Clear caches and mark semantic components stale after indexing."""
    from searchat.api import dependencies as deps

    api_state.clear_query_caches()

    engine = deps._search_engine
    if engine is not None:
        engine.refresh_index()

    readiness = get_readiness()
    readiness.set_component("metadata", "idle")
    readiness.set_component("faiss", "idle")
    readiness.set_component("embedder", "idle")

    start_background_warmup()


def trigger_search_engine_warmup() -> None:
    """Trigger async warmup for semantic components if possible."""
    start_background_warmup()
