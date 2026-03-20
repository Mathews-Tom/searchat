"""Health check endpoints for operational monitoring."""
from __future__ import annotations

import os
import shutil
import time
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

import searchat.api.dependencies as deps
from searchat.api.contracts import (
    serialize_health_deep_payload,
    serialize_health_live_payload,
    serialize_health_ready_payload,
)
from searchat.api.readiness import get_readiness

router = APIRouter()


@router.get("/health/live")
async def health_live() -> dict[str, str]:
    return serialize_health_live_payload()


@router.get("/health/ready")
async def health_ready() -> JSONResponse:
    snap = get_readiness().snapshot()
    critical = ("duckdb", "parquet", "search_engine", "metadata")
    errors: dict[str, str] = {}
    for name in critical:
        state = snap.components.get(name, "idle")
        if state == "error":
            errors[name] = snap.errors.get(name, "unknown error")
        elif state != "ready":
            errors[name] = f"not ready (state={state})"

    ready = len(errors) == 0
    payload = serialize_health_ready_payload(
        ready=ready,
        components=dict(snap.components),
        errors=errors,
    )
    status_code = 200 if ready else 503
    return JSONResponse(content=payload, status_code=status_code)


@router.get("/health")
async def health_deep() -> JSONResponse:
    checks: dict[str, dict[str, Any]] = {}
    checks["duckdb"] = _timed_check("duckdb", _check_duckdb)
    checks["faiss"] = _timed_check("faiss", _check_faiss)
    checks["embedder"] = _timed_check("embedder", _check_embedder)
    checks["data_directory"] = _timed_check("data_directory", _check_data_directory)
    checks["backup_directory"] = _timed_check("backup_directory", _check_backup_directory)
    checks["disk_space"] = _timed_check("disk_space", _check_disk_space)

    healthy = all(c["status"] == "ok" for c in checks.values())
    payload = serialize_health_deep_payload(healthy=healthy, checks=checks)
    status_code = 200 if healthy else 503
    return JSONResponse(content=payload, status_code=status_code)


# ---------------------------------------------------------------------------
# Private check functions
# ---------------------------------------------------------------------------


def _timed_check(name: str, fn: Any) -> dict[str, Any]:
    start = time.perf_counter()
    try:
        result = fn()
    except Exception as exc:
        elapsed = (time.perf_counter() - start) * 1000
        return {"status": "error", "latency_ms": round(elapsed, 2), "error": str(exc)}
    result["latency_ms"] = round((time.perf_counter() - start) * 1000, 2)
    return result


def _check_duckdb() -> dict[str, Any]:
    store = deps.get_duckdb_store()
    store.validate_parquet_scan()
    count = store.count_conversations()
    return {"status": "ok", "conversations": count}


def _check_faiss() -> dict[str, Any]:
    engine = deps._search_engine
    if engine is None:
        return {"status": "error", "error": "search engine not loaded"}
    faiss_index = getattr(engine, "faiss_index", None)
    if faiss_index is None:
        return {"status": "error", "error": "FAISS index not loaded"}
    ntotal = faiss_index.ntotal
    if ntotal == 0:
        return {"status": "warning", "vectors": 0}
    return {"status": "ok", "vectors": ntotal}


def _check_embedder() -> dict[str, Any]:
    engine = deps._search_engine
    if engine is None:
        return {"status": "error", "error": "search engine not loaded"}
    embedder = getattr(engine, "embedder", None)
    if embedder is None:
        return {"status": "error", "error": "embedder not loaded"}
    return {"status": "ok"}


def _check_data_directory() -> dict[str, Any]:
    search_dir = deps.get_search_dir()
    data_dir = search_dir / "data"
    if not data_dir.exists():
        return {"status": "error", "error": "data directory missing"}
    parquets = list(data_dir.glob("*.parquet"))
    if not parquets:
        return {"status": "error", "error": "no parquet files found"}
    readable = os.access(data_dir, os.R_OK)
    if not readable:
        return {"status": "error", "error": "data directory not readable"}
    return {"status": "ok", "parquet_files": len(parquets)}


def _check_backup_directory() -> dict[str, Any]:
    manager = deps.get_backup_manager()
    backup_dir = manager.backup_dir
    if not backup_dir.exists():
        return {"status": "error", "error": "backup directory missing"}
    writable = os.access(backup_dir, os.W_OK)
    if not writable:
        return {"status": "error", "error": "backup directory not writable"}
    return {"status": "ok", "path": str(backup_dir)}


def _check_disk_space() -> dict[str, Any]:
    search_dir = deps.get_search_dir()
    usage = shutil.disk_usage(search_dir)
    free_gb = usage.free / (1024**3)
    if free_gb < 0.1:
        return {"status": "error", "free_gb": round(free_gb, 2)}
    if free_gb < 1.0:
        return {"status": "warning", "free_gb": round(free_gb, 2)}
    return {"status": "ok", "free_gb": round(free_gb, 2)}
