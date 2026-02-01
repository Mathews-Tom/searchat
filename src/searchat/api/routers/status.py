"""Status endpoints - readiness and warmup state."""

from datetime import datetime, timezone

from fastapi import APIRouter

import searchat.api.dependencies as deps
from searchat.api.readiness import get_readiness


router = APIRouter()


_SERVER_STARTED_AT = datetime.now(timezone.utc).isoformat()


@router.get("/status")
async def get_status():
    """Return current readiness state for UI polling and diagnostics."""
    snap = get_readiness().snapshot()
    return {
        "server_started_at": _SERVER_STARTED_AT,
        "warmup_started_at": snap.warmup_started_at,
        "components": snap.components,
        "watcher": snap.watcher,
        "errors": snap.errors,
    }


@router.get("/status/features")
async def get_features():
    """Return feature flag snapshot for the UI."""
    config = deps.get_config()
    return {
        "analytics": {
            "enabled": config.analytics.enabled,
        },
        "chat": {
            "enable_rag": config.chat.enable_rag,
            "enable_citations": config.chat.enable_citations,
        },
        "export": {
            "enable_ipynb": config.export.enable_ipynb,
            "enable_pdf": config.export.enable_pdf,
            "enable_tech_docs": config.export.enable_tech_docs,
        },
        "dashboards": {
            "enabled": config.dashboards.enabled,
        },
        "snapshots": {
            "enabled": config.snapshots.enabled,
        },
    }
