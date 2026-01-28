"""Statistics endpoint - index statistics and metadata."""

import logging
from fastapi import APIRouter, HTTPException, Query

import searchat.api.dependencies as deps


logger = logging.getLogger(__name__)


router = APIRouter()


@router.get("/statistics")
async def get_statistics():
    """Get search index statistics."""
    if deps.stats_cache is None:
        store = deps.get_duckdb_store()
        stats = store.get_statistics()
        deps.stats_cache = {
            "total_conversations": stats.total_conversations,
            "total_messages": stats.total_messages,
            "avg_messages": stats.avg_messages,
            "total_projects": stats.total_projects,
            "earliest_date": stats.earliest_date,
            "latest_date": stats.latest_date,
        }
    return deps.stats_cache


@router.get("/stats/analytics/summary")
async def get_analytics_summary(
    days: int = Query(7, description="Number of days to analyze (1-90)", ge=1, le=90)
):
    """Get search analytics summary for the past N days."""
    try:
        analytics = deps.get_analytics_service()
        return analytics.get_stats_summary(days=days)
    except Exception as e:
        logger.error(f"Failed to get analytics summary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats/analytics/top-queries")
async def get_top_queries(
    limit: int = Query(10, description="Number of queries to return (1-50)", ge=1, le=50),
    days: int = Query(7, description="Number of days to analyze (1-90)", ge=1, le=90)
):
    """Get most frequent search queries."""
    try:
        analytics = deps.get_analytics_service()
        return {
            "queries": analytics.get_top_queries(limit=limit, days=days),
            "days": days
        }
    except Exception as e:
        logger.error(f"Failed to get top queries: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats/analytics/dead-ends")
async def get_dead_end_queries(
    limit: int = Query(10, description="Number of queries to return (1-50)", ge=1, le=50),
    days: int = Query(7, description="Number of days to analyze (1-90)", ge=1, le=90)
):
    """Get queries that returned few or no results (dead ends)."""
    try:
        analytics = deps.get_analytics_service()
        return {
            "queries": analytics.get_dead_end_queries(limit=limit, days=days),
            "days": days
        }
    except Exception as e:
        logger.error(f"Failed to get dead-end queries: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
