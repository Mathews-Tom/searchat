// Save and restore search state

export function saveSearchState() {
    const state = {
        query: document.getElementById('search').value,
        mode: document.getElementById('mode').value,
        project: document.getElementById('project').value,
        tool: document.getElementById('tool').value,
        date: document.getElementById('date').value,
        dateFrom: document.getElementById('dateFrom').value,
        dateTo: document.getElementById('dateTo').value,
        sortBy: document.getElementById('sortBy').value
    };
    sessionStorage.setItem('searchState', JSON.stringify(state));
    sessionStorage.setItem('lastView', 'search');
}

export function saveAllConversationsState() {
    const state = {
        project: document.getElementById('project').value,
        tool: document.getElementById('tool').value,
        date: document.getElementById('date').value,
        dateFrom: document.getElementById('dateFrom').value,
        dateTo: document.getElementById('dateTo').value,
        sortBy: document.getElementById('sortBy').value
    };
    sessionStorage.setItem('allConversationsState', JSON.stringify(state));
    sessionStorage.setItem('lastView', 'all');
}

export async function restoreSearchState() {
    const lastView = sessionStorage.getItem('lastView');
    if (lastView === 'all') {
        const stateStr = sessionStorage.getItem('allConversationsState');
        if (!stateStr) return false;

        const state = JSON.parse(stateStr);
        document.getElementById('project').value = state.project || '';
        document.getElementById('tool').value = state.tool || '';
        document.getElementById('date').value = state.date || '';
        document.getElementById('dateFrom').value = state.dateFrom || '';
        document.getElementById('dateTo').value = state.dateTo || '';
        document.getElementById('sortBy').value = state.sortBy || 'relevance';

        const { toggleCustomDate, showAllConversations } = await import('./search.js');
        toggleCustomDate();

        await showAllConversations();
        return true;
    }

    const stateStr = sessionStorage.getItem('searchState');
    if (!stateStr) return false;

    const state = JSON.parse(stateStr);
    document.getElementById('search').value = state.query || '';
    document.getElementById('mode').value = state.mode || 'hybrid';
    document.getElementById('project').value = state.project || '';
    document.getElementById('tool').value = state.tool || '';
    document.getElementById('date').value = state.date || '';
    document.getElementById('dateFrom').value = state.dateFrom || '';
    document.getElementById('dateTo').value = state.dateTo || '';
    document.getElementById('sortBy').value = state.sortBy || 'relevance';

    // Show custom date range if needed
    const { toggleCustomDate } = await import('./search.js');
    toggleCustomDate();

    const hasFilters = Boolean(
        state.query ||
        state.project ||
        state.tool ||
        state.date ||
        state.dateFrom ||
        state.dateTo
    );

    // Re-run the search to restore results with proper click handlers
    if (hasFilters) {
        const { search } = await import('./search.js');
        search();
        return true;
    }

    return false;
}
