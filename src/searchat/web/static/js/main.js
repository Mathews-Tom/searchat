// Main Entry Point

import { initTheme, setTheme } from './modules/theme.js';
import { restoreSearchState } from './modules/session.js';
import { loadProjects } from './modules/api.js';
import { search, toggleCustomDate, loadConversationView, showSearchView, initProjectSuggestion } from './modules/search.js';
import { initChat } from './modules/chat.js';
import { initShortcuts, toggleHelpModal } from './modules/shortcuts.js';
import { initSearchHistory, restoreSearchFromHistory, clearHistory } from './modules/search-history.js';
import { copyCode } from './modules/code-extraction.js';
import { initSuggestions } from './modules/suggestions.js';
import { initBookmarks, showBookmarks } from './modules/bookmarks.js';
import { showAnalytics } from './modules/analytics.js';
import { goToPage } from './modules/pagination.js';
import { initSavedQueries } from './modules/saved-queries.js';
import { showDashboards } from './modules/dashboards.js';
import { initDatasetSelector } from './modules/dataset.js';

// Make functions globally available for inline event handlers
window.setTheme = setTheme;
window.search = search;
window.toggleCustomDate = toggleCustomDate;
window.toggleHelpModal = toggleHelpModal;
window.restoreSearchFromHistory = restoreSearchFromHistory;
window.clearSearchHistory = clearHistory;
window.copyCode = copyCode;
window.showBookmarks = showBookmarks;
window.toggleBulkMode = function () {
    throw new Error('Bulk export module not loaded');
};
window.showAnalytics = showAnalytics;
window.showDashboards = showDashboards;
window.goToPage = (page) => goToPage(page, search);

function safeInit(name, fn) {
    try {
        const result = fn();
        if (result && typeof result.then === 'function') {
            result.catch((error) => {
                console.error(`Init failed: ${name}`, error);
            });
        }
    } catch (error) {
        console.error(`Init failed: ${name}`, error);
    }
}

// Initialize modules on page load. A failure in one module should not
// break basic interactions like search and chat.
safeInit('theme', initTheme);
safeInit('chat', initChat);
safeInit('shortcuts', initShortcuts);
safeInit('search-history', initSearchHistory);
safeInit('suggestions', initSuggestions);
safeInit('bookmarks', initBookmarks);
safeInit('saved-queries', initSavedQueries);
safeInit('project-suggestion', initProjectSuggestion);
safeInit('dataset-selector', initDatasetSelector);

safeInit('bulk-export', async () => {
    const module = await import('./modules/bulk-export.js');
    window.toggleBulkMode = module.toggleBulkMode;
    module.initBulkExport();
});

// Import and expose other functions that might be called from HTML
import('./modules/backup.js').then(module => {
    window.createBackup = module.createBackup;
    window.showBackups = module.showBackups;
});

import('./modules/api.js').then(module => {
    window.indexMissing = module.indexMissing;
    window.shutdownServer = module.shutdownServer;
});

import('./modules/search.js').then(module => {
    window.showAllConversations = module.showAllConversations;
    window.resumeSession = module.resumeSession;
});

// Add event listener for search on Enter key
const searchBox = document.getElementById('search');
if (searchBox) {
    searchBox.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') search();
    });
}

// On page load, restore state if available
window.addEventListener('load', async () => {
    const activeConversationId = sessionStorage.getItem('activeConversationId');
    const match = window.location.pathname.match(/\/conversation\/([^/]+)/);
    const conversationId = (match && match[1]) ? match[1] : activeConversationId;
    if (conversationId) {
        await loadConversationView(conversationId, false);
        return;
    }

    await loadProjects();

    // Check if we're returning from a conversation view
    const searchState = sessionStorage.getItem('searchState');
    if (searchState) {
        await restoreSearchState();

        // After search completes, restore position and highlight
        setTimeout(() => {
            const scrollPos = sessionStorage.getItem('lastScrollPosition');
            if (scrollPos) {
                window.scrollTo(0, parseInt(scrollPos));
            }

            // Highlight last clicked result
            const lastIndex = sessionStorage.getItem('lastResultIndex');
            if (lastIndex) {
                const element = document.getElementById(`result-${lastIndex}`);
                if (element) {
                    element.style.border = '2px solid #4CAF50';
                }
            }
        }, 500);
    }

    sessionStorage.removeItem('activeConversationId');
});

window.addEventListener('popstate', async () => {
    const match = window.location.pathname.match(/\/conversation\/([^/]+)/);
    if (match && match[1]) {
        await loadConversationView(match[1], false);
        return;
    }

    showSearchView();
    await restoreSearchState();
});
