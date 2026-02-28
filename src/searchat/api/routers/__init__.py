"""FastAPI route handlers organized by resource."""
from searchat.api.routers.search import router as search_router
from searchat.api.routers.conversations import router as conversations_router
from searchat.api.routers.bookmarks import router as bookmarks_router
from searchat.api.routers.stats import router as stats_router
from searchat.api.routers.indexing import router as indexing_router
from searchat.api.routers.backup import router as backup_router
from searchat.api.routers.admin import router as admin_router
from searchat.api.routers.status import router as status_router
from searchat.api.routers.chat import router as chat_router
from searchat.api.routers.queries import router as queries_router
from searchat.api.routers.code import router as code_router
from searchat.api.routers.docs import router as docs_router
from searchat.api.routers.patterns import router as patterns_router
from searchat.api.routers.dashboards import router as dashboards_router
from searchat.api.routers.expertise import router as expertise_router

__all__ = [
    "search_router",
    "conversations_router",
    "bookmarks_router",
    "stats_router",
    "indexing_router",
    "backup_router",
    "admin_router",
    "status_router",
    "chat_router",
    "queries_router",
    "code_router",
    "docs_router",
    "patterns_router",
    "dashboards_router",
    "expertise_router",
]
