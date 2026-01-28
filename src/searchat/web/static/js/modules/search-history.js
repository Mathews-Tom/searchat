// Search History with LocalStorage

const HISTORY_KEY = 'searchat_search_history';
const MAX_HISTORY = 20;

/**
 * Get search history from localStorage
 */
function getHistory() {
    try {
        const history = localStorage.getItem(HISTORY_KEY);
        return history ? JSON.parse(history) : [];
    } catch (e) {
        console.error('Failed to load search history:', e);
        return [];
    }
}

/**
 * Save search history to localStorage
 */
function saveHistory(history) {
    try {
        localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
    } catch (e) {
        console.error('Failed to save search history:', e);
    }
}

/**
 * Add search to history
 */
export function addToHistory(searchParams) {
    const history = getHistory();

    // Create search entry
    const entry = {
        query: searchParams.query,
        mode: searchParams.mode,
        project: searchParams.project,
        tool: searchParams.tool,
        date: searchParams.date,
        dateFrom: searchParams.dateFrom,
        dateTo: searchParams.dateTo,
        sortBy: searchParams.sortBy,
        timestamp: new Date().toISOString()
    };

    // Don't add if it's identical to the last search
    if (history.length > 0) {
        const last = history[0];
        if (last.query === entry.query &&
            last.mode === entry.mode &&
            last.project === entry.project &&
            last.tool === entry.tool &&
            last.date === entry.date) {
            return;
        }
    }

    // Add to beginning
    history.unshift(entry);

    // Keep only MAX_HISTORY entries
    if (history.length > MAX_HISTORY) {
        history.length = MAX_HISTORY;
    }

    saveHistory(history);
    updateHistoryUI();
}

/**
 * Clear search history
 */
export function clearHistory() {
    localStorage.removeItem(HISTORY_KEY);
    updateHistoryUI();
}

/**
 * Initialize search history UI
 */
export function initSearchHistory() {
    // Create history dropdown container
    const searchBox = document.getElementById('search');
    if (!searchBox) return;

    const container = document.createElement('div');
    container.id = 'searchHistoryContainer';
    container.style.cssText = `
        position: relative;
        display: none;
        margin-top: 8px;
        background: var(--bg-elevated);
        border: 1px solid var(--border-default);
        border-radius: 8px;
        padding: 8px;
        max-height: 400px;
        overflow-y: auto;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
        z-index: 100;
    `;

    // Insert after search controls
    const searchControls = document.querySelector('.search-controls');
    if (searchControls) {
        searchControls.parentNode.insertBefore(container, searchControls.nextSibling);
    }

    // Add toggle button
    const toggleBtn = document.createElement('button');
    toggleBtn.id = 'historyToggle';
    toggleBtn.textContent = '🕐 Recent Searches';
    toggleBtn.style.cssText = `
        margin-top: 8px;
        padding: 6px 12px;
        background: var(--bg-surface);
        border: 1px solid var(--border-default);
        border-radius: 6px;
        color: var(--text-primary);
        font-family: 'Space Grotesk', sans-serif;
        font-size: 13px;
        cursor: pointer;
        transition: all 0.2s;
    `;
    toggleBtn.onmouseover = () => {
        toggleBtn.style.background = 'var(--bg-elevated)';
    };
    toggleBtn.onmouseout = () => {
        toggleBtn.style.background = 'var(--bg-surface)';
    };
    toggleBtn.onclick = toggleHistoryUI;

    if (searchControls) {
        searchControls.parentNode.insertBefore(toggleBtn, container);
    }

    updateHistoryUI();
}

/**
 * Toggle history UI visibility
 */
function toggleHistoryUI() {
    const container = document.getElementById('searchHistoryContainer');
    if (!container) return;

    const isVisible = container.style.display !== 'none';
    container.style.display = isVisible ? 'none' : 'block';

    const btn = document.getElementById('historyToggle');
    if (btn) {
        btn.textContent = isVisible ? '🕐 Recent Searches' : '✕ Close History';
    }

    if (!isVisible) {
        updateHistoryUI();
    }
}

/**
 * Update history UI with current history
 */
function updateHistoryUI() {
    const container = document.getElementById('searchHistoryContainer');
    if (!container) return;

    const history = getHistory();

    if (history.length === 0) {
        container.innerHTML = `
            <div style="color: var(--text-muted); font-size: 13px; text-align: center; padding: 16px;">
                No recent searches yet
            </div>
        `;
        return;
    }

    let html = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px solid var(--border-muted);">
            <div style="color: var(--text-primary); font-weight: 500; font-size: 13px;">
                Recent Searches
            </div>
            <button onclick="window.clearSearchHistory()" style="
                background: transparent;
                border: none;
                color: var(--text-muted);
                font-size: 12px;
                cursor: pointer;
                padding: 4px 8px;
                border-radius: 4px;
                transition: all 0.2s;
            " onmouseover="this.style.background='var(--bg-surface)'" onmouseout="this.style.background='transparent'">
                Clear All
            </button>
        </div>
    `;

    history.forEach((entry, index) => {
        const date = new Date(entry.timestamp);
        const timeAgo = getTimeAgo(date);

        // Build filter summary
        const filters = [];
        if (entry.mode && entry.mode !== 'hybrid') filters.push(`mode: ${entry.mode}`);
        if (entry.project) filters.push(`project: ${entry.project}`);
        if (entry.tool) filters.push(`tool: ${entry.tool}`);
        if (entry.date && entry.date !== 'all') filters.push(`date: ${entry.date}`);

        const filterText = filters.length > 0 ? filters.join(', ') : 'no filters';

        html += `
            <div class="history-entry" onclick="window.restoreSearchFromHistory(${index})" style="
                padding: 10px;
                margin-bottom: 4px;
                border-radius: 6px;
                cursor: pointer;
                transition: all 0.2s;
                border: 1px solid transparent;
            " onmouseover="this.style.background='var(--bg-surface)'; this.style.borderColor='var(--border-default)'" onmouseout="this.style.background='transparent'; this.style.borderColor='transparent'">
                <div style="color: var(--text-primary); font-size: 14px; margin-bottom: 4px; font-weight: 500;">
                    ${entry.query || '<em style="color: var(--text-muted);">(empty query)</em>'}
                </div>
                <div style="color: var(--text-muted); font-size: 12px;">
                    ${filterText} • ${timeAgo}
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

/**
 * Restore search from history
 */
export function restoreSearchFromHistory(index) {
    const history = getHistory();
    if (index < 0 || index >= history.length) return;

    const entry = history[index];

    // Populate form fields
    document.getElementById('search').value = entry.query || '';
    document.getElementById('mode').value = entry.mode || 'hybrid';
    document.getElementById('project').value = entry.project || '';
    document.getElementById('tool').value = entry.tool || '';
    document.getElementById('date').value = entry.date || 'all';
    document.getElementById('sortBy').value = entry.sortBy || 'relevance';

    // Handle custom date range
    if (entry.date === 'custom') {
        document.getElementById('dateFrom').value = entry.dateFrom || '';
        document.getElementById('dateTo').value = entry.dateTo || '';
        if (window.toggleCustomDate) {
            window.toggleCustomDate();
        }
    }

    // Close history UI
    const container = document.getElementById('searchHistoryContainer');
    if (container) {
        container.style.display = 'none';
    }
    const btn = document.getElementById('historyToggle');
    if (btn) {
        btn.textContent = '🕐 Recent Searches';
    }

    // Trigger search
    if (window.search) {
        window.search();
    }
}

/**
 * Get human-readable time ago string
 */
function getTimeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);

    if (seconds < 60) return 'just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    if (seconds < 2592000) return `${Math.floor(seconds / 86400)}d ago`;
    return date.toLocaleDateString();
}
