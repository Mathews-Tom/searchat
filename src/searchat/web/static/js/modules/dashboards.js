// Dashboards Module

import { loadConversationView, showSearchView } from './search.js';
import { restoreSearchState } from './session.js';

let _handlersBound = false;
let _refreshTimer = null;
let _activeDashboardId = null;
let _activeRefreshInterval = null;
let _cachedQueries = [];

function _clearAutoRefresh() {
    if (_refreshTimer) {
        clearInterval(_refreshTimer);
        _refreshTimer = null;
    }
    _activeDashboardId = null;
    _activeRefreshInterval = null;
}

function _escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

function _hideSearchUi() {
    const filtersDiv = document.getElementById('filters');
    const heroElements = [
        document.getElementById('heroTitle'),
        document.getElementById('heroSubtitle'),
        document.getElementById('search')
    ];
    const chatPanel = document.getElementById('chatPanel');

    if (filtersDiv) filtersDiv.style.display = 'none';
    heroElements.forEach(el => { if (el) el.style.display = 'none'; });
    if (chatPanel) chatPanel.style.display = 'none';
    sessionStorage.setItem('lastView', 'dashboard');
}

async function _fetchFeatures() {
    const response = await fetch('/api/status/features');
    if (!response.ok) {
        return null;
    }
    return response.json();
}

async function _fetchDashboards() {
    const response = await fetch('/api/dashboards');
    if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail || 'Failed to load dashboards');
    }
    return response.json();
}

async function _fetchDashboard(dashboardId) {
    const response = await fetch(`/api/dashboards/${dashboardId}`);
    if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail || 'Failed to load dashboard');
    }
    return response.json();
}

async function _fetchSavedQueries() {
    const response = await fetch('/api/queries');
    if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail || 'Failed to load saved queries');
    }
    return response.json();
}

async function _createDashboard(payload) {
    const response = await fetch('/api/dashboards', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    if (!response.ok) {
        const payloadError = await response.json().catch(() => null);
        throw new Error(payloadError?.detail || 'Failed to create dashboard');
    }
    return response.json();
}

async function _updateDashboard(dashboardId, payload) {
    const response = await fetch(`/api/dashboards/${dashboardId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    if (!response.ok) {
        const payloadError = await response.json().catch(() => null);
        throw new Error(payloadError?.detail || 'Failed to update dashboard');
    }
    return response.json();
}

async function _deleteDashboard(dashboardId) {
    const response = await fetch(`/api/dashboards/${dashboardId}`, { method: 'DELETE' });
    if (!response.ok) {
        const payloadError = await response.json().catch(() => null);
        throw new Error(payloadError?.detail || 'Failed to delete dashboard');
    }
}

async function _renderDashboard(dashboardId, container) {
    container.innerHTML = '<div class="dashboard-loading">Loading dashboard...</div>';
    const response = await fetch(`/api/dashboards/${dashboardId}/render`);
    if (!response.ok) {
        const payloadError = await response.json().catch(() => null);
        throw new Error(payloadError?.detail || 'Failed to render dashboard');
    }
    const data = await response.json();
    const dashboard = data.dashboard || {};
    const widgets = Array.isArray(data.widgets) ? data.widgets : [];

    const refreshInterval = Number.isFinite(dashboard.refresh_interval) ? dashboard.refresh_interval : null;

    const cards = widgets.map(widget => {
        const results = Array.isArray(widget.results) ? widget.results : [];
        const list = results.length
            ? results.map(result => `
                <div class="dashboard-result-item">
                    <div class="dashboard-result-main">
                        <div class="dashboard-result-title">${_escapeHtml(result.title || 'Untitled')}</div>
                        <div class="dashboard-result-meta">${_escapeHtml(result.project_id || 'unknown')} · ${_escapeHtml(result.tool || '')} · ${result.message_count || 0} msgs</div>
                        <div class="dashboard-result-snippet">${_escapeHtml(result.snippet || '')}</div>
                    </div>
                    <a class="dashboard-result-open" href="/conversation/${result.conversation_id}" data-conversation-id="${result.conversation_id}">Open</a>
                </div>
            `).join('')
            : '<div class="dashboard-empty">No results yet.</div>';

        return `
            <div class="dashboard-widget">
                <div class="dashboard-widget-header">
                    <div>
                        <div class="dashboard-widget-title">${_escapeHtml(widget.title || 'Saved Query')}</div>
                        <div class="dashboard-widget-meta">${_escapeHtml(widget.query || '')} · ${widget.total || 0} results</div>
                    </div>
                    <div class="dashboard-widget-tag">${_escapeHtml(widget.mode || 'hybrid')}</div>
                </div>
                <div class="dashboard-widget-body">${list}</div>
            </div>
        `;
    }).join('');

    container.innerHTML = `
        <div class="dashboard-view-header">
            <div>
                <h2>${_escapeHtml(dashboard.name || 'Dashboard')}</h2>
                <p>${_escapeHtml(dashboard.description || '')}</p>
                ${refreshInterval ? `<p style="margin-top: 6px; font-size: 12px; color: hsl(var(--text-tertiary));">Auto-refresh: every ${refreshInterval}s</p>` : ''}
            </div>
            <div class="dashboard-view-actions">
                <button class="secondary" data-action="refresh" data-dashboard-id="${dashboardId}">Refresh</button>
                <button class="secondary" data-action="edit" data-dashboard-id="${dashboardId}">Edit</button>
                <a class="secondary" href="/api/dashboards/${dashboardId}/export">Export JSON</a>
            </div>
        </div>
        <div class="dashboard-grid">${cards || '<div class="dashboard-empty">No widgets configured.</div>'}</div>
    `;

    _configureAutoRefresh(dashboardId, refreshInterval, container);
}

function _renderDashboardBuilder(dashboard, container) {
    const widgets = Array.isArray(dashboard?.layout?.widgets) ? dashboard.layout.widgets : [];
    const columns = Number.isFinite(dashboard?.layout?.columns) ? dashboard.layout.columns : '';
    const refreshInterval = Number.isFinite(dashboard?.refresh_interval) ? dashboard.refresh_interval : '';

    container.innerHTML = `
        <div class="dashboard-builder">
            <div class="dashboard-builder-header">
                <div>
                    <div class="dashboard-builder-title">Edit Dashboard</div>
                    <div class="dashboard-builder-subtitle">Update widgets, layout, and refresh settings.</div>
                </div>
                <div class="dashboard-builder-actions">
                    <button class="secondary" data-action="builder-cancel" data-dashboard-id="${dashboard.id}">Cancel</button>
                    <button data-action="builder-save" data-dashboard-id="${dashboard.id}">Save</button>
                </div>
            </div>

            <div class="dashboard-builder-form">
                <input type="text" id="dashboardEditName" value="${_escapeHtml(dashboard.name || '')}" placeholder="Dashboard name" />
                <input type="text" id="dashboardEditDescription" value="${_escapeHtml(dashboard.description || '')}" placeholder="Description (optional)" />
                <input type="number" id="dashboardEditRefresh" value="${refreshInterval}" placeholder="Refresh interval (seconds)" min="1" />
                <input type="number" id="dashboardEditColumns" value="${columns}" placeholder="Columns (1-6)" min="1" max="6" />
            </div>

            <div class="dashboard-builder-widgets" id="dashboardBuilderWidgets">
                ${widgets.map(w => _renderWidgetEditorRow(w)).join('')}
            </div>

            <div class="dashboard-builder-footer">
                <button class="secondary" data-action="builder-add-widget" data-dashboard-id="${dashboard.id}">Add Widget</button>
                <div class="dashboard-status" id="dashboardBuilderStatus"></div>
            </div>
        </div>
    `;
}

function _renderWidgetEditorRow(widget) {
    const queryId = widget?.query_id || '';
    const title = widget?.title || '';
    const limit = Number.isFinite(widget?.limit) ? widget.limit : '';
    const sortBy = widget?.sort_by || '';
    const widgetId = widget?.id || '';

    const queryOptions = _cachedQueries.map(q => {
        const selected = q.id === queryId ? 'selected' : '';
        return `<option value="${q.id}" ${selected}>${_escapeHtml(q.name)} — ${_escapeHtml(q.query)}</option>`;
    }).join('');

    return `
        <div class="dashboard-builder-widget" data-widget-id="${_escapeHtml(widgetId)}">
            <div class="dashboard-builder-widget-grid">
                <select class="dashboard-widget-query" aria-label="Saved query">
                    <option value="">Select saved query...</option>
                    ${queryOptions}
                </select>
                <input class="dashboard-widget-title" type="text" value="${_escapeHtml(title)}" placeholder="Widget title (optional)" />
                <input class="dashboard-widget-limit" type="number" value="${limit}" min="1" max="100" placeholder="Limit" />
                <select class="dashboard-widget-sort" aria-label="Sort">
                    <option value="" ${sortBy === '' ? 'selected' : ''}>Sort (default)</option>
                    <option value="relevance" ${sortBy === 'relevance' ? 'selected' : ''}>Relevance</option>
                    <option value="date_newest" ${sortBy === 'date_newest' ? 'selected' : ''}>Newest</option>
                    <option value="date_oldest" ${sortBy === 'date_oldest' ? 'selected' : ''}>Oldest</option>
                    <option value="messages" ${sortBy === 'messages' ? 'selected' : ''}>Messages</option>
                </select>
            </div>
            <div class="dashboard-builder-widget-actions">
                <button class="secondary" data-action="builder-move-up">↑</button>
                <button class="secondary" data-action="builder-move-down">↓</button>
                <button class="secondary danger" data-action="builder-remove-widget">Remove</button>
            </div>
        </div>
    `;
}

function _appendWidgetEditor(container) {
    const widgetsDiv = container.querySelector('#dashboardBuilderWidgets');
    if (!widgetsDiv) return;
    const newWidget = { id: `ui-${Date.now()}`, query_id: '', title: '', limit: 5, sort_by: '' };
    widgetsDiv.insertAdjacentHTML('beforeend', _renderWidgetEditorRow(newWidget));
}

function _collectBuilderState(container) {
    const name = container.querySelector('#dashboardEditName')?.value?.trim() || '';
    if (!name) {
        throw new Error('Dashboard name is required.');
    }

    const description = container.querySelector('#dashboardEditDescription')?.value?.trim() || '';
    const refreshRaw = container.querySelector('#dashboardEditRefresh')?.value?.trim() || '';
    const columnsRaw = container.querySelector('#dashboardEditColumns')?.value?.trim() || '';

    const refreshInterval = refreshRaw ? Number.parseInt(refreshRaw, 10) : null;
    const columns = columnsRaw ? Number.parseInt(columnsRaw, 10) : null;

    const widgetRows = Array.from(container.querySelectorAll('.dashboard-builder-widget'));
    const widgets = widgetRows.map(row => {
        const queryId = row.querySelector('.dashboard-widget-query')?.value?.trim() || '';
        const title = row.querySelector('.dashboard-widget-title')?.value?.trim() || '';
        const limitRaw = row.querySelector('.dashboard-widget-limit')?.value?.trim() || '';
        const sortBy = row.querySelector('.dashboard-widget-sort')?.value?.trim() || '';
        const widgetId = row.dataset.widgetId || '';

        return {
            id: widgetId || null,
            query_id: queryId,
            title: title || null,
            limit: limitRaw ? Number.parseInt(limitRaw, 10) : null,
            sort_by: sortBy || null
        };
    });

    if (!widgets.length) {
        throw new Error('At least one widget is required.');
    }
    for (const widget of widgets) {
        if (!widget.query_id) {
            throw new Error('Each widget must select a saved query.');
        }
    }

    const queryIds = [];
    for (const widget of widgets) {
        if (!queryIds.includes(widget.query_id)) {
            queryIds.push(widget.query_id);
        }
    }

    return {
        name,
        description: description || null,
        refresh_interval: Number.isFinite(refreshInterval) ? refreshInterval : null,
        queries: queryIds,
        layout: {
            widgets,
            columns: Number.isFinite(columns) ? columns : null
        }
    };
}

function _configureAutoRefresh(dashboardId, refreshInterval, container) {
    const interval = Number.isFinite(refreshInterval) ? refreshInterval : null;
    if (!interval || interval <= 0) {
        _clearAutoRefresh();
        return;
    }

    if (_activeDashboardId === dashboardId && _activeRefreshInterval === interval && _refreshTimer) {
        return;
    }

    _clearAutoRefresh();
    _activeDashboardId = dashboardId;
    _activeRefreshInterval = interval;
    _refreshTimer = setInterval(async () => {
        if (_activeDashboardId !== dashboardId) return;
        try {
            await _renderDashboard(dashboardId, container);
        } catch (error) {
            // If refresh fails, stop looping to avoid spamming the server.
            _clearAutoRefresh();
        }
    }, interval * 1000);
}

function _renderPage(container, dashboards, savedQueries) {
    const queries = Array.isArray(savedQueries) ? savedQueries : [];
    const list = Array.isArray(dashboards) ? dashboards : [];

    const savedQueriesHtml = queries.length
        ? queries.map(query => `
            <label class="dashboard-query-option">
                <input type="checkbox" value="${query.id}" />
                <span>${_escapeHtml(query.name)} <small>${_escapeHtml(query.query)}</small></span>
            </label>
        `).join('')
        : '<div class="dashboard-empty">No saved queries yet. Save a query to build widgets.</div>';

    const dashboardsHtml = list.length
        ? list.map(dashboard => `
            <div class="dashboard-card" data-dashboard-id="${dashboard.id}">
                <div>
                    <div class="dashboard-card-title">${_escapeHtml(dashboard.name)}</div>
                    <div class="dashboard-card-meta">${_escapeHtml(dashboard.description || '')}</div>
                </div>
                <div class="dashboard-card-actions">
                    <button data-action="view" data-dashboard-id="${dashboard.id}">View</button>
                    <button data-action="edit" data-dashboard-id="${dashboard.id}" class="secondary">Edit</button>
                    <button data-action="delete" data-dashboard-id="${dashboard.id}" class="danger">Delete</button>
                </div>
            </div>
        `).join('')
        : '<div class="dashboard-empty">No dashboards yet.</div>';

    container.innerHTML = `
        <div class="dashboard-header">
            <div>
                <h2>Dashboards</h2>
                <p>Track saved queries as live widgets.</p>
            </div>
            <button class="link" data-action="back">← Back to Search</button>
        </div>

        <div class="dashboard-panel">
            <h3>Create Dashboard</h3>
            <div class="dashboard-form">
                <input type="text" id="dashboardName" placeholder="Dashboard name" />
                <input type="text" id="dashboardDescription" placeholder="Description (optional)" />
                <input type="number" id="dashboardRefresh" placeholder="Refresh interval (seconds)" min="1" />
            </div>
            <div class="dashboard-queries">
                ${savedQueriesHtml}
            </div>
            <div class="dashboard-form-actions">
                <button data-action="create">Create Dashboard</button>
            </div>
            <div class="dashboard-status" id="dashboardStatus"></div>
        </div>

        <div class="dashboard-panel">
            <h3>Saved Dashboards</h3>
            <div class="dashboard-list">${dashboardsHtml}</div>
        </div>

        <div class="dashboard-panel" id="dashboardView"></div>
    `;
}

function _collectSelectedQueries() {
    const queryInputs = document.querySelectorAll('.dashboard-queries input[type="checkbox"]');
    const selected = [];
    queryInputs.forEach(input => {
        if (input.checked) {
            selected.push(input.value);
        }
    });
    return selected;
}

export async function showDashboards() {
    const resultsDiv = document.getElementById('results');
    if (!resultsDiv) return;
    _hideSearchUi();
    resultsDiv.innerHTML = '<div class="dashboard-loading">Loading dashboards...</div>';

    try {
        const features = await _fetchFeatures();
        if (!features?.dashboards?.enabled) {
            resultsDiv.innerHTML = `
                <div class="dashboard-panel">
                    <h2>Dashboards</h2>
                    <p>Dashboards are disabled. Enable <code>[dashboards].enabled = true</code> in <code>~/.searchat/config/settings.toml</code> to use this feature.</p>
                    <button class="link" data-action="back">← Back to Search</button>
                </div>
            `;
        } else {
            const [dashboardsData, queriesData] = await Promise.all([
                _fetchDashboards(),
                _fetchSavedQueries()
            ]);
            _cachedQueries = Array.isArray(queriesData.queries) ? queriesData.queries : [];
            _renderPage(resultsDiv, dashboardsData.dashboards, queriesData.queries);
        }

        if (!_handlersBound) {
            resultsDiv.addEventListener('click', async (event) => {
            const target = event.target;
            if (!(target instanceof HTMLElement)) return;
            const action = target.dataset.action;
            const dashboardId = target.dataset.dashboardId;

            if (action === 'back') {
                _clearAutoRefresh();
                showSearchView();
                const restored = await restoreSearchState();
                if (!restored) {
                    sessionStorage.removeItem('lastView');
                    showSearchView();
                }
                return;
            }

            if (action === 'create') {
                const status = document.getElementById('dashboardStatus');
                const name = document.getElementById('dashboardName').value.trim();
                if (!name) {
                    if (status) status.textContent = 'Dashboard name is required.';
                    return;
                }
                const description = document.getElementById('dashboardDescription').value.trim();
                const refreshRaw = document.getElementById('dashboardRefresh').value.trim();
                const refreshInterval = refreshRaw ? Number.parseInt(refreshRaw, 10) : null;
                const queryIds = _collectSelectedQueries();
                if (!queryIds.length) {
                    if (status) status.textContent = 'Select at least one saved query.';
                    return;
                }

                const widgets = queryIds.map(queryId => ({ query_id: queryId }));
                const payload = {
                    name,
                    description: description || null,
                    refresh_interval: Number.isFinite(refreshInterval) ? refreshInterval : null,
                    queries: queryIds,
                    layout: { widgets }
                };

                try {
                    await _createDashboard(payload);
                    const [dashboardsData, queriesData] = await Promise.all([
                        _fetchDashboards(),
                        _fetchSavedQueries()
                    ]);
                    _renderPage(resultsDiv, dashboardsData.dashboards, queriesData.queries);
                } catch (error) {
                    if (status) status.textContent = error.message;
                }
            }

            if (action === 'view' && dashboardId) {
                const view = document.getElementById('dashboardView');
                if (!view) return;
                try {
                    await _renderDashboard(dashboardId, view);
                } catch (error) {
                    view.innerHTML = `<div class="dashboard-empty">${_escapeHtml(error.message)}</div>`;
                }
            }

            if (action === 'edit' && dashboardId) {
                const view = document.getElementById('dashboardView');
                if (!view) return;
                try {
                    const data = await _fetchDashboard(dashboardId);
                    const dashboard = data.dashboard;
                    if (!dashboard) {
                        throw new Error('Dashboard not found');
                    }
                    _renderDashboardBuilder(dashboard, view);
                } catch (error) {
                    view.innerHTML = `<div class="dashboard-empty">${_escapeHtml(error.message)}</div>`;
                }
            }

            if (action === 'refresh' && dashboardId) {
                const view = document.getElementById('dashboardView');
                if (!view) return;
                try {
                    await _renderDashboard(dashboardId, view);
                } catch (error) {
                    view.innerHTML = `<div class="dashboard-empty">${_escapeHtml(error.message)}</div>`;
                }
            }

            if (action === 'delete' && dashboardId) {
                const confirmed = window.confirm('Delete this dashboard?');
                if (!confirmed) return;
                try {
                    await _deleteDashboard(dashboardId);
                    const [dashboardsData, queriesData] = await Promise.all([
                        _fetchDashboards(),
                        _fetchSavedQueries()
                    ]);
                    _renderPage(resultsDiv, dashboardsData.dashboards, queriesData.queries);
                } catch (error) {
                    const status = document.getElementById('dashboardStatus');
                    if (status) status.textContent = error.message;
                }
            }

            if (action === 'builder-add-widget' && dashboardId) {
                const view = document.getElementById('dashboardView');
                if (!view) return;
                _appendWidgetEditor(view);
            }

            if (action === 'builder-remove-widget') {
                const row = target.closest('.dashboard-builder-widget');
                if (row) {
                    row.remove();
                }
            }

            if (action === 'builder-move-up' || action === 'builder-move-down') {
                const row = target.closest('.dashboard-builder-widget');
                if (!row) return;
                if (action === 'builder-move-up' && row.previousElementSibling) {
                    row.parentNode.insertBefore(row, row.previousElementSibling);
                }
                if (action === 'builder-move-down' && row.nextElementSibling) {
                    row.parentNode.insertBefore(row.nextElementSibling, row);
                }
            }

            if (action === 'builder-cancel' && dashboardId) {
                const view = document.getElementById('dashboardView');
                if (!view) return;
                try {
                    await _renderDashboard(dashboardId, view);
                } catch (error) {
                    view.innerHTML = `<div class="dashboard-empty">${_escapeHtml(error.message)}</div>`;
                }
            }

            if (action === 'builder-save' && dashboardId) {
                const view = document.getElementById('dashboardView');
                if (!view) return;
                const status = view.querySelector('#dashboardBuilderStatus');
                if (status) status.textContent = '';
                try {
                    const payload = _collectBuilderState(view);
                    await _updateDashboard(dashboardId, payload);
                    const [dashboardsData, queriesData] = await Promise.all([
                        _fetchDashboards(),
                        _fetchSavedQueries()
                    ]);
                    _cachedQueries = Array.isArray(queriesData.queries) ? queriesData.queries : [];
                    _renderPage(resultsDiv, dashboardsData.dashboards, queriesData.queries);

                    const nextView = document.getElementById('dashboardView');
                    if (nextView) {
                        await _renderDashboard(dashboardId, nextView);
                    }
                } catch (error) {
                    if (status) status.textContent = error.message;
                }
            }

            if (target.classList.contains('dashboard-result-open')) {
                event.preventDefault();
                const conversationId = target.dataset.conversationId;
                if (conversationId) {
                    await loadConversationView(conversationId);
                }
            }
        });
            _handlersBound = true;
        }
    } catch (error) {
        resultsDiv.innerHTML = `<div class="dashboard-empty">Failed to load dashboards: ${_escapeHtml(error.message)}</div>`;
    }
}
