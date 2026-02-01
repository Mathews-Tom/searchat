/**
 * Splash Screen Module
 *
 * Displays an informative splash screen during system warmup (first visit only).
 * Shows system highlights, component loading progress, and links to full infographics.
 */

const SPLASH_STORAGE_KEY = 'searchatSplashDismissedServerStartedAt';
const LEGACY_SPLASH_STORAGE_KEY = 'searchatSplashShown';
const STATUS_POLL_INTERVAL = 500; // ms
const CRITICAL_COMPONENTS = ['embedder', 'faiss', 'metadata'];

// 8-12 key highlights with icons (medium summary)
const HIGHLIGHTS = [
    { icon: '🔍', title: '3 Search Modes', desc: 'Hybrid, Semantic, Keyword' },
    { icon: '⚡', title: '<100ms Search', desc: 'Ultra-fast hybrid search with RRF fusion' },
    { icon: '🎯', title: 'Autocomplete', desc: 'Smart suggestions as you type' },
    { icon: '🤖', title: '8 AI Agents', desc: 'Claude, Vibe, OpenCode, Codex, Gemini, Continue, Cursor, Aider' },
    { icon: '🔌', title: 'MCP Server', desc: 'Native integration for MCP clients' },
    { icon: '💬', title: 'RAG Chat', desc: 'AI-powered Q&A over conversation history' },
    { icon: '🔗', title: 'Similarity Search', desc: 'Discover related conversations' },
    { icon: '🔖', title: 'Bookmarks', desc: 'Save and annotate favorites' },
    { icon: '📊', title: 'Analytics', desc: 'Track search patterns and trends' },
    { icon: '📥', title: 'Export', desc: 'JSON, Markdown, Text, PDF formats' },
    { icon: '🛡️', title: 'Append-Only', desc: 'Never deletes existing data' },
    { icon: '💾', title: 'Auto-Backup', desc: 'Safe system backups' },
    { icon: '📈', title: '50+ API Endpoints', desc: 'Comprehensive REST API' },
];

let pollInterval = null;
let _currentServerStartedAt = null;

/**
 * Check if user has seen splash before
 */
function hasDismissedSplashForServer(serverStartedAt) {
    if (!serverStartedAt) return false;
    try {
        return localStorage.getItem(SPLASH_STORAGE_KEY) === String(serverStartedAt);
    } catch (error) {
        console.warn('Splash: failed to read localStorage', error);
        return false;
    }
}

/**
 * Mark splash as seen (persistent across sessions)
 */
function markSplashDismissedForServer(serverStartedAt) {
    if (!serverStartedAt) return;
    try {
        localStorage.setItem(SPLASH_STORAGE_KEY, String(serverStartedAt));
    } catch (error) {
        console.warn('Splash: failed to write localStorage', error);
    }
}

function clearLegacySplashFlag() {
    try {
        localStorage.removeItem(LEGACY_SPLASH_STORAGE_KEY);
    } catch (error) {
        console.warn('Splash: failed to clear legacy localStorage key', error);
    }
}

/**
 * Check warmup status and show splash if needed (first visit only)
 */
export async function checkAndShowSplash() {
    try {
        clearLegacySplashFlag();

        const response = await fetch('/api/status');
        const status = await response.json();

        const serverStartedAt = status.server_started_at || status.warmup_started_at;
        _currentServerStartedAt = serverStartedAt || null;

        // Show splash once per server start (requires manual dismissal).
        if (hasDismissedSplashForServer(_currentServerStartedAt)) {
            return;
        }

        renderSplash(status);
        pollWarmupStatus();
    } catch (error) {
        console.error('Failed to check warmup status:', error);
    }
}

/**
 * Render splash overlay with highlights and progress
 */
function renderSplash(status) {
    // Create overlay
    const overlay = document.createElement('div');
    overlay.id = 'splashOverlay';
    overlay.className = 'splash-overlay';

    // Create content card
    const content = document.createElement('div');
    content.className = 'splash-content';

    // Header
    const header = document.createElement('div');
    header.className = 'splash-header';
    header.innerHTML = `
        <h1><span style="color: #4a9eff">sear</span><span style="background: linear-gradient(to right, #4a9eff, #ff9500); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">ch</span><span style="color: #ff9500">at</span></h1>
        <p>Warming up search engine...</p>
    `;
    content.appendChild(header);

    // Highlights grid
    const highlightsContainer = document.createElement('div');
    highlightsContainer.className = 'splash-highlights';
    HIGHLIGHTS.forEach(highlight => {
        const item = document.createElement('div');
        item.className = 'splash-highlight-item';
        item.innerHTML = `
            <span class="splash-highlight-icon">${highlight.icon}</span>
            <div class="splash-highlight-text">
                <div class="splash-highlight-title">${highlight.title}</div>
                <div class="splash-highlight-desc">${highlight.desc}</div>
            </div>
        `;
        highlightsContainer.appendChild(item);
    });
    content.appendChild(highlightsContainer);

    // Progress container
    const progressContainer = document.createElement('div');
    progressContainer.id = 'splashProgress';
    progressContainer.className = 'splash-progress-container';
    content.appendChild(progressContainer);

    // Actions
    const actions = document.createElement('div');
    actions.className = 'splash-actions';
    actions.innerHTML = `
        <a href="/docs/infographics.html" target="_blank" class="splash-btn splash-btn-secondary">
            View Full Infographics
        </a>
        <button id="splashDismiss" class="splash-btn splash-btn-primary">
            Get Started
        </button>
    `;
    content.appendChild(actions);

    overlay.appendChild(content);
    document.body.appendChild(overlay);

    // Manual dismiss (always required; never auto-dismiss)
    const dismissBtn = document.getElementById('splashDismiss');
    if (dismissBtn) {
        dismissBtn.onclick = dismissSplash;
    }

    // Initial progress render
    updateProgress(status);

    // Fade in animation
    setTimeout(() => overlay.classList.add('splash-visible'), 10);
}

/**
 * Update progress indicators based on status
 */
function updateProgress(status) {
    const container = document.getElementById('splashProgress');
    if (!container) return;

    // Clear existing progress items
    container.innerHTML = '';

    // Component display order (prioritize critical ones)
    const componentOrder = [
        'services',
        'duckdb',
        'parquet',
        'search_engine',
        'embedder',
        'faiss',
        'metadata',
        'indexer'
    ];

    componentOrder.forEach(name => {
        const state = status.components[name];
        if (!state) return;

        const item = renderProgressItem(name, state, status.errors[name]);
        container.appendChild(item);
    });
}

/**
 * Render individual progress item with spinner and bar
 */
function renderProgressItem(name, state, error) {
    const item = document.createElement('div');
    item.className = 'splash-progress-item';

    // Component icon based on state
    let icon = '';
    if (state === 'ready') {
        icon = '✓';
    } else if (state === 'error') {
        icon = '✗';
    } else {
        icon = '⏳';
    }

    // Progress percentage based on state
    let progress = 0;
    let statusText = '';
    if (state === 'ready') {
        progress = 100;
        statusText = 'Ready';
    } else if (state === 'loading') {
        progress = 60;
        statusText = 'Loading...';
    } else if (state === 'error') {
        progress = 0;
        statusText = error || 'Error';
    } else {
        progress = 0;
        statusText = 'Idle';
    }

    // Spinner (hidden for ready/error states)
    const showSpinner = state === 'loading' || state === 'idle';
    const spinnerHtml = showSpinner
        ? '<div class="splash-spinner" aria-hidden="true"></div>'
        : '';

    item.innerHTML = `
        <span class="splash-progress-icon">${icon}</span>
        <span class="splash-progress-name">${formatComponentName(name)}</span>
        ${spinnerHtml}
        <div class="splash-progress-bar">
            <div class="splash-progress-fill" style="width: ${progress}%"></div>
        </div>
        <span class="splash-progress-status">${statusText}</span>
    `;

    // Add state class for styling
    item.classList.add(`splash-progress-${state}`);

    return item;
}

/**
 * Format component name for display
 */
function formatComponentName(name) {
    const names = {
        'services': 'Services',
        'duckdb': 'Database',
        'parquet': 'Data Files',
        'search_engine': 'Search Engine',
        'faiss': 'FAISS Index',
        'metadata': 'Metadata',
        'embedder': 'AI Embeddings',
        'indexer': 'Indexer'
    };
    return names[name] || name;
}

/**
 * Poll warmup status until ready or error
 */
function pollWarmupStatus() {
    if (pollInterval) {
        clearInterval(pollInterval);
    }

    pollInterval = setInterval(async () => {
        try {
            const response = await fetch('/api/status');
            const status = await response.json();

            // Update progress display
            updateProgress(status);

            const criticalReady = CRITICAL_COMPONENTS.every(
                name => status.components[name] === 'ready'
            );

            // Once ready, stop polling to reduce overhead. Overlay stays until user dismisses.
            if (criticalReady && pollInterval) {
                clearInterval(pollInterval);
                pollInterval = null;
            }
        } catch (error) {
            console.error('Failed to poll status:', error);
        }
    }, STATUS_POLL_INTERVAL);
}

/**
 * Dismiss splash screen and mark as seen
 */
function dismissSplash() {
    // Clear intervals and timeouts
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
    markSplashDismissedForServer(_currentServerStartedAt);

    // Fade out and remove
    const overlay = document.getElementById('splashOverlay');
    if (overlay) {
        overlay.classList.remove('splash-visible');
        setTimeout(() => overlay.remove(), 300);
    }
}
