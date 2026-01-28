// Search suggestions / autocomplete

let suggestionsTimeout = null;
let activeSuggestionIndex = -1;

/**
 * Initialize search suggestions
 */
export function initSuggestions() {
    const searchBox = document.getElementById('search');
    if (!searchBox) return;

    // Create suggestions dropdown
    const container = document.createElement('div');
    container.id = 'suggestionsContainer';
    container.style.cssText = `
        position: absolute;
        display: none;
        background: var(--bg-elevated);
        border: 1px solid var(--border-default);
        border-radius: 8px;
        margin-top: 4px;
        max-height: 300px;
        overflow-y: auto;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
        z-index: 1000;
        min-width: 400px;
    `;

    // Position container below search box
    searchBox.parentNode.style.position = 'relative';
    searchBox.parentNode.appendChild(container);

    // Add input event listener
    searchBox.addEventListener('input', (e) => {
        const query = e.target.value.trim();

        if (query.length < 2) {
            hideSuggestions();
            return;
        }

        // Debounce API calls
        clearTimeout(suggestionsTimeout);
        suggestionsTimeout = setTimeout(() => {
            fetchSuggestions(query);
        }, 300);
    });

    // Handle keyboard navigation
    searchBox.addEventListener('keydown', (e) => {
        const container = document.getElementById('suggestionsContainer');
        if (!container || container.style.display === 'none') return;

        const items = container.querySelectorAll('.suggestion-item');
        if (items.length === 0) return;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            activeSuggestionIndex = Math.min(activeSuggestionIndex + 1, items.length - 1);
            updateActiveSuggestion(items);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            activeSuggestionIndex = Math.max(activeSuggestionIndex - 1, -1);
            updateActiveSuggestion(items);
        } else if (e.key === 'Enter' && activeSuggestionIndex >= 0) {
            e.preventDefault();
            items[activeSuggestionIndex].click();
        } else if (e.key === 'Escape') {
            hideSuggestions();
        }
    });

    // Close suggestions when clicking outside
    document.addEventListener('click', (e) => {
        const searchBox = document.getElementById('search');
        const container = document.getElementById('suggestionsContainer');
        if (searchBox && container && !searchBox.contains(e.target) && !container.contains(e.target)) {
            hideSuggestions();
        }
    });
}

/**
 * Fetch suggestions from API
 */
async function fetchSuggestions(query) {
    const container = document.getElementById('suggestionsContainer');
    if (!container) return;

    try {
        const response = await fetch(`/api/search/suggestions?q=${encodeURIComponent(query)}&limit=10`);
        if (!response.ok) {
            hideSuggestions();
            return;
        }

        const data = await response.json();

        if (!data.suggestions || data.suggestions.length === 0) {
            hideSuggestions();
            return;
        }

        displaySuggestions(data.suggestions, query);

    } catch (error) {
        console.error('Failed to fetch suggestions:', error);
        hideSuggestions();
    }
}

/**
 * Display suggestions in dropdown
 */
function displaySuggestions(suggestions, query) {
    const container = document.getElementById('suggestionsContainer');
    if (!container) return;

    activeSuggestionIndex = -1;

    let html = `
        <div style="
            padding: 8px 12px;
            border-bottom: 1px solid var(--border-muted);
            color: var(--text-muted);
            font-size: 12px;
            font-weight: 500;
        ">
            SUGGESTIONS
        </div>
    `;

    suggestions.forEach((suggestion, index) => {
        // Highlight matching part
        const highlighted = highlightMatch(suggestion, query);

        html += `
            <div class="suggestion-item" data-suggestion="${escapeHtml(suggestion)}" style="
                padding: 10px 12px;
                cursor: pointer;
                transition: background 0.2s;
                border-bottom: 1px solid var(--border-muted);
                color: var(--text-primary);
                font-size: 14px;
            " onmouseover="this.style.background='var(--bg-surface)'" onmouseout="this.style.background='transparent'">
                ${highlighted}
            </div>
        `;
    });

    // Remove border from last item
    html = html.replace(/border-bottom: 1px solid var\(--border-muted\);(?![\s\S]*border-bottom)/, '');

    container.innerHTML = html;
    container.style.display = 'block';

    // Add click handlers
    container.querySelectorAll('.suggestion-item').forEach(item => {
        item.addEventListener('click', () => {
            const searchBox = document.getElementById('search');
            if (searchBox) {
                searchBox.value = item.dataset.suggestion;
                hideSuggestions();

                // Trigger search
                if (window.search) {
                    window.search();
                }
            }
        });
    });
}

/**
 * Highlight matching part of suggestion
 */
function highlightMatch(text, query) {
    const index = text.toLowerCase().indexOf(query.toLowerCase());
    if (index === -1) return escapeHtml(text);

    const before = escapeHtml(text.substring(0, index));
    const match = escapeHtml(text.substring(index, index + query.length));
    const after = escapeHtml(text.substring(index + query.length));

    return `${before}<strong style="color: var(--accent-primary); font-weight: 600;">${match}</strong>${after}`;
}

/**
 * Update active suggestion highlight
 */
function updateActiveSuggestion(items) {
    items.forEach((item, index) => {
        if (index === activeSuggestionIndex) {
            item.style.background = 'var(--bg-surface)';
            item.scrollIntoView({ block: 'nearest' });

            // Update search box with active suggestion
            const searchBox = document.getElementById('search');
            if (searchBox) {
                searchBox.value = item.dataset.suggestion;
            }
        } else {
            item.style.background = 'transparent';
        }
    });
}

/**
 * Hide suggestions dropdown
 */
function hideSuggestions() {
    const container = document.getElementById('suggestionsContainer');
    if (container) {
        container.style.display = 'none';
    }
    activeSuggestionIndex = -1;
}

/**
 * Escape HTML entities
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
