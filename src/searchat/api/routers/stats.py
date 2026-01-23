"""Statistics endpoint - index statistics and metadata."""
from fastapi import APIRouter

from searchat.api.dependencies import get_search_engine


router = APIRouter()


@router.get("/statistics")
async def get_statistics():
    """Get search index statistics."""
    search_engine = get_search_engine()
    df = search_engine.conversations_df

    return {
        "total_conversations": len(df),
        "total_messages": int(df['message_count'].sum()),
        "avg_messages": float(df['message_count'].mean()),
        "total_projects": int(df['project_id'].nunique()),
        "earliest_date": df['created_at'].min().isoformat() if not df.empty else None,
        "latest_date": df['updated_at'].max().isoformat() if not df.empty else None
    }
