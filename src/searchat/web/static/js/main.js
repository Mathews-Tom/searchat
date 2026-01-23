// Main Entry Point

import { initTheme, setTheme } from './modules/theme.js';
import { restoreSearchState } from './modules/session.js';
import { loadProjects } from './modules/api.js';
import { search, toggleCustomDate } from './modules/search.js';

// Initialize theme on page load
initTheme();

// Make functions globally available for inline event handlers
window.setTheme = setTheme;
window.search = search;
window.toggleCustomDate = toggleCustomDate;

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
document.getElementById('search').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') search();
});

// On page load, restore state if available
window.addEventListener('load', async () => {
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
});
