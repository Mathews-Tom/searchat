// Saved queries functionality (hybrid local + backend)

const LOCAL_KEY = 'savedQueries';
let _savedQueries = [];
let _pendingQueryState = null;

function _escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function _loadLocalQueries() {
    try {
        const raw = localStorage.getItem(LOCAL_KEY);
        return raw ? JSON.parse(raw) : [];
    } catch (error) {
        console.error('Failed to load saved queries from local storage', error);
        return [];
    }
}

function _saveLocalQueries(queries) {
    localStorage.setItem(LOCAL_KEY, JSON.stringify(queries));
}

function _setStatus(message) {
    const status = document.getElementById('savedQueriesStatus');
    if (status) {
        status.textContent = message || '';
    }
}

function _getCurrentSearchState() {
    return {
        query: document.getElementById('search').value,
        mode: document.getElementById('mode').value,
        filters: {
            project: document.getElementById('project').value,
            tool: document.getElementById('tool').value,
            date: document.getElementById('date').value,
            date_from: document.getElementById('dateFrom').value,
            date_to: document.getElementById('dateTo').value,
            sort_by: document.getElementById('sortBy').value
        }
    };
}

function _applyQueryToForm(savedQuery) {
    document.getElementById('search').value = savedQuery.query || '';
    document.getElementById('mode').value = savedQuery.mode || 'hybrid';
    document.getElementById('project').value = savedQuery.filters?.project || '';
    document.getElementById('tool').value = savedQuery.filters?.tool || '';
    document.getElementById('date').value = savedQuery.filters?.date || '';
    document.getElementById('sortBy').value = savedQuery.filters?.sort_by || 'relevance';
    document.getElementById('dateFrom').value = savedQuery.filters?.date_from || '';
    document.getElementById('dateTo').value = savedQuery.filters?.date_to || '';
    if (typeof window.toggleCustomDate === 'function') {
        window.toggleCustomDate();
    }
}

function _renderSavedQueries() {
    const list = document.getElementById('savedQueriesList');
    if (!list) return;

    if (!_savedQueries.length) {
        list.innerHTML = '<div class="saved-queries-status">No saved queries yet.</div>';
        return;
    }

    list.innerHTML = _savedQueries.map((query) => {
        const desc = query.description ? ` - ${_escapeHtml(query.description)}` : '';
        const modeLabel = query.mode ? _escapeHtml(query.mode) : '';
        const projectLabel = query.filters?.project ? ` • ${_escapeHtml(query.filters.project)}` : '';
        const meta = `${modeLabel}${projectLabel}`;
        const syncLabel = query.synced === false ? ' (local only)' : '';
        return `
            <div class="saved-query-item" data-query-id="${query.id}">
                <div class="saved-query-title">${_escapeHtml(query.name)}${syncLabel}</div>
                <div class="saved-query-meta">${meta}${desc}</div>
                <div class="saved-query-actions">
                    <button class="saved-query-run" data-query-id="${query.id}">Run</button>
                    <button class="saved-query-edit" data-query-id="${query.id}">Edit</button>
                    <button class="saved-query-delete" data-query-id="${query.id}">Delete</button>
                </div>
            </div>
        `;
    }).join('');
}

function _openForm(state) {
    _pendingQueryState = state;
    const form = document.getElementById('savedQueriesForm');
    if (form) form.style.display = 'grid';
    document.getElementById('savedQueryName').value = state?.name || '';
    document.getElementById('savedQueryDescription').value = state?.description || '';
}

function _closeForm() {
    _pendingQueryState = null;
    const form = document.getElementById('savedQueriesForm');
    if (form) form.style.display = 'none';
    document.getElementById('savedQueryName').value = '';
    document.getElementById('savedQueryDescription').value = '';
}

async function _fetchSavedQueries() {
    try {
        const response = await fetch('/api/queries');
        if (!response.ok) {
            const payload = await response.json().catch(() => null);
            throw new Error(payload?.detail || 'Failed to load saved queries');
        }
        const data = await response.json();
        return Array.isArray(data.queries) ? data.queries.map(q => ({ ...q, synced: true })) : [];
    } catch (error) {
        _setStatus('Saved queries are available locally only.');
        return null;
    }
}

async function _createBackendQuery(payload) {
    const response = await fetch('/api/queries', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    if (!response.ok) {
        const payloadError = await response.json().catch(() => null);
        throw new Error(payloadError?.detail || 'Failed to save query');
    }
    const data = await response.json();
    return data.query;
}

async function _updateBackendQuery(queryId, payload) {
    const response = await fetch(`/api/queries/${queryId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    if (!response.ok) {
        const payloadError = await response.json().catch(() => null);
        throw new Error(payloadError?.detail || 'Failed to update query');
    }
    const data = await response.json();
    return data.query;
}

async function _deleteBackendQuery(queryId) {
    const response = await fetch(`/api/queries/${queryId}`, { method: 'DELETE' });
    if (!response.ok) {
        const payloadError = await response.json().catch(() => null);
        throw new Error(payloadError?.detail || 'Failed to delete query');
    }
}

async function _recordBackendRun(queryId) {
    await fetch(`/api/queries/${queryId}/run`, { method: 'POST' });
}

function _syncLocal(queries) {
    _savedQueries = queries;
    _saveLocalQueries(_savedQueries);
    _renderSavedQueries();
}

function _findQuery(queryId) {
    return _savedQueries.find(query => query.id === queryId);
}

export async function initSavedQueries() {
    const localQueries = _loadLocalQueries();
    const backendQueries = await _fetchSavedQueries();

    if (backendQueries) {
        _syncLocal(backendQueries);
        _setStatus('');
    } else {
        _syncLocal(localQueries);
    }

    const saveButtons = [
        document.getElementById('saveQueryButton'),
        document.getElementById('saveQueryButtonInline')
    ].filter(Boolean);

    saveButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            _openForm(_getCurrentSearchState());
        });
    });

    document.getElementById('savedQueryCancel').addEventListener('click', () => {
        _closeForm();
    });

    document.getElementById('savedQuerySave').addEventListener('click', async () => {
        const name = document.getElementById('savedQueryName').value.trim();
        if (!name) {
            _setStatus('Name is required to save a query.');
            return;
        }

        const description = document.getElementById('savedQueryDescription').value.trim();
        const baseState = _pendingQueryState || _getCurrentSearchState();

        const payload = {
            name,
            description: description || null,
            query: baseState.query,
            filters: baseState.filters,
            mode: baseState.mode
        };

        try {
            if (baseState.id) {
                const updated = await _updateBackendQuery(baseState.id, payload);
                const updatedList = _savedQueries.map(q => q.id === baseState.id ? { ...updated, synced: true } : q);
                _syncLocal(updatedList);
            } else {
                const localId = `local-${Date.now()}`;
                const localEntry = { ...payload, id: localId, created_at: new Date().toISOString(), last_used: null, use_count: 0, synced: false };
                _syncLocal([localEntry, ..._savedQueries]);

                const created = await _createBackendQuery(payload);
                const merged = _savedQueries.map(q => q.id === localId ? { ...created, synced: true } : q);
                _syncLocal(merged);
            }
            _setStatus('');
            _closeForm();
        } catch (error) {
            _setStatus(error.message);
        }
    });

    document.getElementById('savedQueriesList').addEventListener('click', async (event) => {
        const target = event.target;
        if (!target.dataset.queryId) return;
        const queryId = target.dataset.queryId;
        const savedQuery = _findQuery(queryId);
        if (!savedQuery) return;

        if (target.classList.contains('saved-query-run')) {
            _applyQueryToForm(savedQuery);
            window.search();
            const updatedList = _savedQueries.map(q => {
                if (q.id !== queryId) return q;
                return {
                    ...q,
                    last_used: new Date().toISOString(),
                    use_count: (q.use_count || 0) + 1
                };
            });
            _syncLocal(updatedList);
            if (!queryId.startsWith('local-')) {
                _recordBackendRun(queryId).catch(() => null);
            }
        }

        if (target.classList.contains('saved-query-edit')) {
            _openForm(savedQuery);
            _pendingQueryState.id = savedQuery.id;
        }

        if (target.classList.contains('saved-query-delete')) {
            const updatedList = _savedQueries.filter(q => q.id !== queryId);
            _syncLocal(updatedList);
            if (!queryId.startsWith('local-')) {
                try {
                    await _deleteBackendQuery(queryId);
                } catch (error) {
                    _setStatus(error.message);
                }
            }
        }
    });
}
