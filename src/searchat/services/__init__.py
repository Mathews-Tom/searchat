"""External integrations and utilities."""
from searchat.services.analytics import SearchAnalyticsService
from searchat.services.backup import BackupManager
from searchat.services.bookmarks import BookmarksService
from searchat.services.dashboards import DashboardsService
from searchat.services.platform_utils import PlatformManager
from searchat.services.saved_queries import SavedQueriesService

__all__ = [
    "SearchAnalyticsService",
    "BackupManager",
    "BookmarksService",
    "DashboardsService",
    "PlatformManager",
    "SavedQueriesService",
]
