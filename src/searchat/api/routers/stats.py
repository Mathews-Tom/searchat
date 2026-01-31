"""Statistics endpoint - index statistics and metadata."""

import logging
from fastapi import APIRouter, HTTPException, Query

import searchat.api.dependencies as deps


logger = logging.getLogger(__name__)


router = APIRouter()


@router.get("/statistics")
async def get_statistics(snapshot: str | None = Query(None, description="Backup snapshot name (read-only)")):
    """Get search index statistics."""
    try:
        search_dir, snapshot_name = deps.resolve_dataset_search_dir(snapshot)
    except ValueError as exc:
        msg = str(exc)
        if msg == "Snapshot not found":
            raise HTTPException(status_code=404, detail="Snapshot not found") from exc
        raise HTTPException(status_code=400, detail=msg) from exc
    store = deps.get_duckdb_store_for(search_dir)

    if snapshot_name is not None:
        stats = store.get_statistics()
        return {
            "total_conversations": stats.total_conversations,
            "total_messages": stats.total_messages,
            "avg_messages": stats.avg_messages,
            "total_projects": stats.total_projects,
            "earliest_date": stats.earliest_date,
            "latest_date": stats.latest_date,
        }

    if deps.stats_cache is None:
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
    days: int = Query(7, description="Number of days to analyze (1-90)", ge=1, le=90),
    snapshot: str | None = Query(None, description="Backup snapshot name (read-only)"),
):
    """Get search analytics summary for the past N days."""
    if snapshot is not None:
        raise HTTPException(status_code=403, detail="Analytics is available only for the active dataset")
    try:
        analytics = deps.get_analytics_service()
        return analytics.get_stats_summary(days=days)
    except Exception as e:
        logger.error(f"Failed to get analytics summary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats/analytics/top-queries")
async def get_top_queries(
    limit: int = Query(10, description="Number of queries to return (1-50)", ge=1, le=50),
    days: int = Query(7, description="Number of days to analyze (1-90)", ge=1, le=90),
    snapshot: str | None = Query(None, description="Backup snapshot name (read-only)"),
):
    """Get most frequent search queries."""
    if snapshot is not None:
        raise HTTPException(status_code=403, detail="Analytics is available only for the active dataset")
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
    days: int = Query(7, description="Number of days to analyze (1-90)", ge=1, le=90),
    snapshot: str | None = Query(None, description="Backup snapshot name (read-only)"),
):
    """Get queries that returned few or no results (dead ends)."""
    if snapshot is not None:
        raise HTTPException(status_code=403, detail="Analytics is available only for the active dataset")
    try:
        analytics = deps.get_analytics_service()
        return {
            "queries": analytics.get_dead_end_queries(limit=limit, days=days),
            "days": days
        }
    except Exception as e:
        logger.error(f"Failed to get dead-end queries: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats/analytics/config")
async def get_analytics_config(snapshot: str | None = Query(None, description="Backup snapshot name (read-only)")):
    """Get analytics config snapshot."""
    if snapshot is not None:
        raise HTTPException(status_code=403, detail="Analytics is available only for the active dataset")
    try:
        config = deps.get_config()
        return {
            "enabled": config.analytics.enabled,
            "retention_days": config.analytics.retention_days,
        }
    except Exception as e:
        logger.error(f"Failed to get analytics config: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats/analytics/trends")
async def get_analytics_trends(
    days: int = Query(30, description="Number of days to analyze (1-90)", ge=1, le=90),
    snapshot: str | None = Query(None, description="Backup snapshot name (read-only)"),
):
    """Get daily search trends."""
    if snapshot is not None:
        raise HTTPException(status_code=403, detail="Analytics is available only for the active dataset")
    try:
        analytics = deps.get_analytics_service()
        return {"days": days, "points": analytics.get_trends(days=days)}
    except Exception as e:
        logger.error(f"Failed to get analytics trends: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats/analytics/heatmap")
async def get_analytics_heatmap(
    days: int = Query(30, description="Number of days to analyze (1-90)", ge=1, le=90),
    snapshot: str | None = Query(None, description="Backup snapshot name (read-only)"),
):
    """Get hour-of-day by day-of-week heatmap."""
    if snapshot is not None:
        raise HTTPException(status_code=403, detail="Analytics is available only for the active dataset")
    try:
        analytics = deps.get_analytics_service()
        return analytics.get_heatmap(days=days)
    except Exception as e:
        logger.error(f"Failed to get analytics heatmap: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats/analytics/agent-comparison")
async def get_analytics_agent_comparison(
    days: int = Query(30, description="Number of days to analyze (1-90)", ge=1, le=90),
    snapshot: str | None = Query(None, description="Backup snapshot name (read-only)"),
):
    """Get tool filter comparison for searches."""
    if snapshot is not None:
        raise HTTPException(status_code=403, detail="Analytics is available only for the active dataset")
    try:
        analytics = deps.get_analytics_service()
        return {"days": days, "tools": analytics.get_agent_comparison(days=days)}
    except Exception as e:
        logger.error(f"Failed to get analytics agent comparison: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats/analytics/topics")
async def get_analytics_topics(
    days: int = Query(30, description="Number of days to analyze (1-90)", ge=1, le=90),
    k: int = Query(8, description="Number of clusters (2-20)", ge=2, le=20),
    snapshot: str | None = Query(None, description="Backup snapshot name (read-only)"),
):
    """Get topic clusters for recent queries."""
    if snapshot is not None:
        raise HTTPException(status_code=403, detail="Analytics is available only for the active dataset")
    try:
        analytics = deps.get_analytics_service()
        return {"days": days, "clusters": analytics.get_topic_clusters(days=days, k=k)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get analytics topics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
