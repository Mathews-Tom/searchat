"""Status endpoints - readiness and warmup state."""

from datetime import datetime, timezone

from fastapi import APIRouter

from searchat.api.contracts import (
    serialize_status_features_payload,
    serialize_status_payload,
)
import searchat.api.dependencies as deps
from searchat.api.readiness import get_readiness
from searchat.api.utils import get_retrieval_capabilities_snapshot


router = APIRouter()


_SERVER_STARTED_AT = datetime.now(timezone.utc).isoformat()


@router.get("/status")
async def get_status():
    """Return current readiness state for UI polling and diagnostics."""
    snap = get_readiness().snapshot()
    return serialize_status_payload(
        server_started_at=_SERVER_STARTED_AT,
        warmup_started_at=snap.warmup_started_at,
        components=snap.components,
        watcher=snap.watcher,
        errors=snap.errors,
        retrieval=get_retrieval_capabilities_snapshot(),
    )


@router.get("/status/features")
async def get_features():
    """Return feature flag snapshot for the UI."""
    config = deps.get_config()
    return serialize_status_features_payload(
        analytics_enabled=config.analytics.enabled,
        chat_enable_rag=config.chat.enable_rag,
        chat_enable_citations=config.chat.enable_citations,
        export_enable_ipynb=config.export.enable_ipynb,
        export_enable_pdf=config.export.enable_pdf,
        export_enable_tech_docs=config.export.enable_tech_docs,
        dashboards_enabled=config.dashboards.enabled,
        snapshots_enabled=config.snapshots.enabled,
        retrieval=get_retrieval_capabilities_snapshot(),
    )
