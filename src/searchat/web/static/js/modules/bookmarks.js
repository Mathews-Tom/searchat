// Bookmarks management

let bookmarkedConversations = new Set();

function bookmarkIconSvg(isBookmarked) {
    const fill = isBookmarked ? 'currentColor' : 'none';
    return `
        <svg class="bookmark-star-icon" width="16" height="16" viewBox="0 0 24 24" fill="${fill}" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="m19 21-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path>
        </svg>
    `;
}

/**
 * Initialize bookmarks
 */
export async function initBookmarks() {
    await loadBookmarkedIds();
}

/**
 * Load bookmarked conversation IDs
 */
async function loadBookmarkedIds() {
    try {
        const response = await fetch('/api/bookmarks');
        if (!response.ok) return;

        const data = await response.json();
        bookmarkedConversations.clear();

        data.bookmarks.forEach(bookmark => {
            bookmarkedConversations.add(bookmark.conversation_id);
        });

    } catch (error) {
        console.error('Failed to load bookmarks:', error);
    }
}

/**
 * Toggle bookmark for a conversation
 */
export async function toggleBookmark(conversationId, starElement) {
    const isBookmarked = bookmarkedConversations.has(conversationId);

    try {
        if (isBookmarked) {
            // Remove bookmark
            const response = await fetch(`/api/bookmarks/${conversationId}`, {
                method: 'DELETE'
            });

            if (!response.ok) {
                throw new Error('Failed to remove bookmark');
            }

            bookmarkedConversations.delete(conversationId);
            updateStarIcon(starElement, false);

        } else {
            // Add bookmark
            const response = await fetch('/api/bookmarks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    conversation_id: conversationId,
                    notes: ''
                })
            });

            if (!response.ok) {
                throw new Error('Failed to add bookmark');
            }

            bookmarkedConversations.add(conversationId);
            updateStarIcon(starElement, true);
        }

    } catch (error) {
        console.error('Failed to toggle bookmark:', error);
        alert('Failed to toggle bookmark. Please try again.');
    }
}

/**
 * Check if a conversation is bookmarked
 */
export function isBookmarked(conversationId) {
    return bookmarkedConversations.has(conversationId);
}

/**
 * Create star icon for bookmarking
 */
export function createStarIcon(conversationId) {
    const star = document.createElement('button');
    star.className = 'bookmark-star';
    star.dataset.conversationId = conversationId;
    star.type = 'button';

    const isFavorited = isBookmarked(conversationId);
    updateStarIcon(star, isFavorited);

    star.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleBookmark(conversationId, star);
    });

    return star;
}

/**
 * Update star icon appearance
 */
function updateStarIcon(element, isBookmarked) {
    if (isBookmarked) {
        element.innerHTML = bookmarkIconSvg(true);
        element.classList.add('active');
        element.title = 'Remove from bookmarks';
        element.setAttribute('aria-label', 'Remove from bookmarks');
    } else {
        element.innerHTML = bookmarkIconSvg(false);
        element.classList.remove('active');
        element.title = 'Add to bookmarks';
        element.setAttribute('aria-label', 'Add to bookmarks');
    }
}

/**
 * Show bookmarks page
 */
export async function showBookmarks() {
    const resultsDiv = document.getElementById('results');
    const header = document.getElementById('conversationHeader');
    const heroTitle = document.getElementById('heroTitle');
    const heroSubtitle = document.getElementById('heroSubtitle');
    const filters = document.getElementById('filters');
    const chatPanel = document.getElementById('chatPanel');

    // Hide main search UI
    if (header) header.style.display = 'none';
    if (heroTitle) heroTitle.style.display = 'none';
    if (heroSubtitle) heroSubtitle.style.display = 'none';
    if (filters) filters.style.display = 'none';
    if (chatPanel) chatPanel.style.display = 'none';

    resultsDiv.innerHTML = '<div class="loading">Loading bookmarks...</div>';

    try {
        const response = await fetch('/api/bookmarks');
        if (!response.ok) {
            throw new Error('Failed to load bookmarks');
        }

        const data = await response.json();

        resultsDiv.innerHTML = '';

        // Header
        const headerDiv = document.createElement('div');
        headerDiv.style.cssText = `
            margin-bottom: 20px;
            padding-bottom: 16px;
            border-bottom: 1px solid hsl(var(--border-glass));
        `;
        headerDiv.innerHTML = `
            <h1 style="margin: 0 0 8px 0; color: hsl(var(--text-primary));">
                Bookmarked Conversations
            </h1>
            <p style="margin: 0; color: hsl(var(--text-secondary)); font-size: 14px;">
                ${data.total} bookmark${data.total !== 1 ? 's' : ''}
            </p>
        `;
        resultsDiv.appendChild(headerDiv);

        if (data.total === 0) {
            const emptyDiv = document.createElement('div');
            emptyDiv.className = 'empty-state';
            emptyDiv.innerHTML = `
                <div class="empty-icon">☆</div>
                <div style="font-size: 16px; margin-bottom: 8px;">No bookmarks yet</div>
                <div style="font-size: 13px;">Star conversations to save them here for quick access</div>
            `;
            resultsDiv.appendChild(emptyDiv);
            return;
        }

        // Display bookmarks
        data.bookmarks.forEach(bookmark => {
            const div = document.createElement('div');
            div.className = 'result';
            div.style.cursor = 'pointer';

            const addedDate = new Date(bookmark.added_at).toLocaleString();

            div.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: start;">
                    <div style="flex: 1;">
                        <div class="result-title">${bookmark.title || 'Untitled'}</div>
                        <div class="result-meta">
                            <span>Project: ${bookmark.project_id || 'Unknown'}</span> •
                            <span>Messages: ${bookmark.message_count || 0}</span> •
                            <span>Bookmarked: ${addedDate}</span>
                        </div>
                    </div>
                    <button class="remove-bookmark-btn glass-btn" style="border-color: hsl(var(--danger)); color: hsl(var(--danger)); font-size: 12px;">
                        Remove
                    </button>
                </div>
            `;

            // Click to view conversation
            div.addEventListener('click', (e) => {
                if (!e.target.classList.contains('remove-bookmark-btn')) {
                    window.location.href = `/conversation/${bookmark.conversation_id}`;
                }
            });

            // Remove bookmark button
            const removeBtn = div.querySelector('.remove-bookmark-btn');
            removeBtn.addEventListener('click', async (e) => {
                e.stopPropagation();

                if (!confirm(`Remove "${bookmark.title}" from bookmarks?`)) {
                    return;
                }

                try {
                    const response = await fetch(`/api/bookmarks/${bookmark.conversation_id}`, {
                        method: 'DELETE'
                    });

                    if (!response.ok) {
                        throw new Error('Failed to remove bookmark');
                    }

                    bookmarkedConversations.delete(bookmark.conversation_id);
                    div.remove();

                    // Update count
                    const countText = headerDiv.querySelector('p');
                    const newTotal = data.total - 1;
                    countText.textContent = `${newTotal} bookmark${newTotal !== 1 ? 's' : ''}`;

                    // Show empty state if no bookmarks left
                    if (resultsDiv.querySelectorAll('.result').length === 0) {
                        showBookmarks();
                    }

                } catch (error) {
                    console.error('Failed to remove bookmark:', error);
                    alert('Failed to remove bookmark. Please try again.');
                }
            });

            resultsDiv.appendChild(div);
        });

    } catch (error) {
        resultsDiv.innerHTML = `<div style="color: hsl(var(--danger));">Error: ${error.message}</div>`;
    }
}
