// Pagination Module
// Handles pagination UI and state for search results

let currentPage = 1;
let totalResults = 0;
let resultsPerPage = 20;
let currentSearchParams = null;

export function initPagination() {
    // Initialize pagination state
    currentPage = 1;
    totalResults = 0;
}

export function setSearchParams(params) {
    currentSearchParams = params;
}

export function setTotalResults(total) {
    totalResults = total;
}

export function getCurrentPage() {
    return currentPage;
}

export function getOffset() {
    return (currentPage - 1) * resultsPerPage;
}

export function renderPagination(resultsContainer, searchFunction) {
    if (totalResults === 0) {
        return;
    }

    const totalPages = Math.ceil(totalResults / resultsPerPage);

    if (totalPages <= 1) {
        return; // No pagination needed
    }

    const paginationHtml = `
        <div class="pagination glass" style="display: flex; justify-content: center; align-items: center; gap: 12px; margin: 32px 0; padding: 20px;">
            <button
                onclick="window.goToPage(1)"
                ${currentPage === 1 ? 'disabled' : ''}
                class="glass-btn"
                title="First page"
            >
                « First
            </button>

            <button
                onclick="window.goToPage(${currentPage - 1})"
                ${currentPage === 1 ? 'disabled' : ''}
                class="glass-btn"
                title="Previous page"
            >
                ‹ Previous
            </button>

            <div style="display: flex; gap: 6px; align-items: center;">
                ${renderPageNumbers(totalPages)}
            </div>

            <button
                onclick="window.goToPage(${currentPage + 1})"
                ${currentPage === totalPages ? 'disabled' : ''}
                class="glass-btn"
                title="Next page"
            >
                Next ›
            </button>

            <button
                onclick="window.goToPage(${totalPages})"
                ${currentPage === totalPages ? 'disabled' : ''}
                class="glass-btn"
                title="Last page"
            >
                Last »
            </button>

            <div style="margin-left: 16px; color: hsl(var(--text-tertiary)); font-size: 14px;">
                Page ${currentPage} of ${totalPages} (${totalResults} results)
            </div>
        </div>
    `;

    resultsContainer.insertAdjacentHTML('beforeend', paginationHtml);
}

function renderPageNumbers(totalPages) {
    const maxVisible = 7;
    const pages = [];

    if (totalPages <= maxVisible) {
        // Show all pages
        for (let i = 1; i <= totalPages; i++) {
            pages.push(i);
        }
    } else {
        // Show first, last, current, and surrounding pages
        if (currentPage <= 4) {
            // Near start
            for (let i = 1; i <= 5; i++) {
                pages.push(i);
            }
            pages.push('...');
            pages.push(totalPages);
        } else if (currentPage >= totalPages - 3) {
            // Near end
            pages.push(1);
            pages.push('...');
            for (let i = totalPages - 4; i <= totalPages; i++) {
                pages.push(i);
            }
        } else {
            // Middle
            pages.push(1);
            pages.push('...');
            for (let i = currentPage - 1; i <= currentPage + 1; i++) {
                pages.push(i);
            }
            pages.push('...');
            pages.push(totalPages);
        }
    }

    return pages.map(page => {
        if (page === '...') {
            return '<span style="color: hsl(var(--text-tertiary)); padding: 8px;">...</span>';
        }

        const isActive = page === currentPage;
        return `
            <button
                onclick="window.goToPage(${page})"
                class="${isActive ? 'glass-btn glass-btn-primary' : 'glass-btn'}"
                style="min-width: 36px;"
            >
                ${page}
            </button>
        `;
    }).join('');
}

export async function goToPage(page, searchFunction) {
    const totalPages = Math.ceil(totalResults / resultsPerPage);

    if (page < 1 || page > totalPages) {
        return;
    }

    currentPage = page;

    // Scroll to top of results
    window.scrollTo({ top: 0, behavior: 'smooth' });

    // Re-run search with new offset
    if (searchFunction) {
        await searchFunction();
    }
}

export function resetPagination() {
    currentPage = 1;
}
