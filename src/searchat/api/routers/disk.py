"""Disk accounting endpoint -- read-only per-agent and Searchat self footprint.

M6 -- Disk manager dashboard. Serves `services/disk_accounting.py`'s report
over HTTP; there is no mutation endpoint anywhere in this router, matching
the milestone's "report first" scope.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from searchat.api.dependencies import get_config, get_search_dir
from searchat.contracts.errors import internal_server_error_message
from searchat.services.disk_accounting import build_disk_accounting_report

router = APIRouter()
logger = logging.getLogger(__name__)


class AgentDiskUsageResponse(BaseModel):
    """Per-connector disk-usage summary."""

    connector: str
    watch_dirs: list[str]
    total_size_bytes: int
    total_file_count: int
    conversation_file_count: int
    indexed_file_count: int
    indexed_size_bytes: int
    unindexed_file_count: int
    unindexed_size_bytes: int
    oldest_conversation_age_days: float | None
    newest_conversation_age_days: float | None
    age_histogram: dict[str, int]


class SubdirectoryUsageResponse(BaseModel):
    """Disk-usage summary for one Searchat self-accounting subdirectory."""

    label: str
    path: str
    exists: bool
    total_size_bytes: int
    file_count: int


class SearchatSelfUsageResponse(BaseModel):
    """Searchat's own `~/.searchat` footprint."""

    search_dir: str
    subdirectories: list[SubdirectoryUsageResponse]
    total_size_bytes: int
    total_file_count: int


class DiskAccountingResponse(BaseModel):
    """Full read-only disk-accounting report."""

    agents: list[AgentDiskUsageResponse]
    searchat_self: SearchatSelfUsageResponse
    generated_at: str


@router.get("/disk", response_model=DiskAccountingResponse)
async def get_disk_accounting() -> DiskAccountingResponse:
    """Read-only per-agent and Searchat self disk-usage report."""
    try:
        report = build_disk_accounting_report(get_search_dir(), get_config())
    except Exception:
        logger.exception("Failed to build disk accounting report")
        raise HTTPException(status_code=500, detail=internal_server_error_message())
    return DiskAccountingResponse(**report.to_dict())
