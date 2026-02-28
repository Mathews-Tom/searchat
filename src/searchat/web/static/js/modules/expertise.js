// Expertise Dashboard Module

import { showSearchView } from './search.js';
import { restoreSearchState } from './session.js';

const PAGE_SIZE = 25;

let _state = {
    page: 0,
    filters: {
        type: '',
        domain: '',
        project: '',
        tags: '',
        severity: '',
        active_only: true,
        q: '',
    },
    selectedRecordId: null,
    activeTab: 'domains',
};

function _escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

function _hideSearchUi() {
    const filtersDiv = document.getElementById('filters');
    const toolbar = document.querySelector('.toolbar');
    const heroElements = [
        document.getElementById('heroTitle'),
        document.getElementById('heroSubtitle'),
    ];
    if (filtersDiv) filtersDiv.style.display = 'none';
    if (toolbar) toolbar.style.display = 'none';
    heroElements.forEach(el => { if (el) el.style.display = 'none'; });
    sessionStorage.setItem('lastView', 'expertise');
}

function _showSearchUi() {
    const filtersDiv = document.getElementById('filters');
    const toolbar = document.querySelector('.toolbar');
    if (filtersDiv) filtersDiv.style.display = '';
    if (toolbar) toolbar.style.display = '';
}

// ── API helpers ──────────────────────────────────────────────────────────────

async function _apiFetch(url) {
    const response = await fetch(url);
    if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail || `Request failed: ${response.status}`);
    }
    return response.json();
}

async function _fetchStatus() {
    return _apiFetch('/api/expertise/status');
}

async function _fetchDomains() {
    return _apiFetch('/api/expertise/domains');
}

async function _fetchRecords(filters, offset = 0, limit = PAGE_SIZE) {
    const params = new URLSearchParams();
    if (filters.domain) params.set('domain', filters.domain);
    if (filters.type) params.set('type', filters.type);
    if (filters.project) params.set('project', filters.project);
    if (filters.tags) params.set('tags', filters.tags);
    if (filters.severity) params.set('severity', filters.severity);
    if (filters.q) params.set('q', filters.q);
    params.set('active_only', String(filters.active_only));
    params.set('limit', String(limit));
    params.set('offset', String(offset));
    return _apiFetch(`/api/expertise?${params.toString()}`);
}

async function _fetchRecord(recordId) {
    return _apiFetch(`/api/expertise/${encodeURIComponent(recordId)}`);
}

async function _fetchLineage(recordId) {
    return _apiFetch(`/api/knowledge-graph/lineage/${encodeURIComponent(recordId)}`);
}

// ── Renderers ────────────────────────────────────────────────────────────────

function _healthBadgeHtml(health) {
    const cls = health === 'healthy' ? 'healthy' : health === 'critical' ? 'critical' : 'warning';
    return `<span class="health-badge health-badge--${cls}">${_escapeHtml(health)}</span>`;
}

function _renderDomainTable(statusData) {
    const domains = Array.isArray(statusData.domains) ? statusData.domains : [];
    if (!domains.length) {
        return '<div class="expertise-empty">No domains found.</div>';
    }

    const rows = domains.map(d => `
        <tr data-domain="${_escapeHtml(d.name)}">
            <td>${_escapeHtml(d.name)}</td>
            <td>${d.record_count ?? 0}</td>
            <td>${d.active_count ?? 0}</td>
            <td>${d.stale_count ?? 0}</td>
            <td>${d.contradiction_count ?? 0}</td>
            <td>${_healthBadgeHtml(d.health || 'healthy')}</td>
        </tr>
    `).join('');

    return `
        <div class="expertise-table-wrap">
            <table class="expertise-table">
                <thead>
                    <tr>
                        <th>Domain</th>
                        <th>Records</th>
                        <th>Active</th>
                        <th>Stale</th>
                        <th>Contradictions</th>
                        <th>Health</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
    `;
}

function _renderStatsRow(statusData) {
    return `
        <div class="expertise-stats-row">
            <div class="expertise-stat-card">
                <span class="expertise-stat-label">Total Records</span>
                <span class="expertise-stat-value">${statusData.total_records ?? 0}</span>
            </div>
            <div class="expertise-stat-card">
                <span class="expertise-stat-label">Active</span>
                <span class="expertise-stat-value">${statusData.active_records ?? 0}</span>
            </div>
            <div class="expertise-stat-card">
                <span class="expertise-stat-label">Domains</span>
                <span class="expertise-stat-value">${(statusData.domains || []).length}</span>
            </div>
        </div>
    `;
}

function _renderFilterBar(domains) {
    const domainOptions = domains.map(d =>
        `<option value="${_escapeHtml(d.name)}">${_escapeHtml(d.name)}</option>`
    ).join('');

    return `
        <div class="expertise-filter-bar" id="expertiseFilterBar">
            <input type="text" id="expertiseSearch" placeholder="Search records..." value="${_escapeHtml(_state.filters.q)}" />
            <select id="expertiseTypeFilter">
                <option value="">All Types</option>
                <option value="convention">Convention</option>
                <option value="pattern">Pattern</option>
                <option value="failure">Failure</option>
                <option value="decision">Decision</option>
                <option value="boundary">Boundary</option>
                <option value="insight">Insight</option>
            </select>
            <select id="expertiseDomainFilter">
                <option value="">All Domains</option>
                ${domainOptions}
            </select>
            <select id="expertiseSeverityFilter">
                <option value="">All Severities</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
            </select>
            <label style="display:flex;align-items:center;gap:6px;font-size:12px;color:hsl(var(--text-tertiary));">
                <input type="checkbox" id="expertiseActiveOnly" ${_state.filters.active_only ? 'checked' : ''} />
                Active only
            </label>
            <button class="glass-btn" id="expertiseApplyFilters">Apply</button>
        </div>
    `;
}

function _renderRecordList(results, total) {
    if (!results.length) {
        return '<div class="expertise-empty">No records match the current filters.</div>';
    }

    const items = results.map(r => {
        const tagsHtml = (r.tags || []).map(t => `<span class="expertise-tag">${_escapeHtml(t)}</span>`).join('');
        const confidence = r.confidence != null ? `${Math.round(r.confidence * 100)}%` : '';
        return `
            <div class="expertise-record-item" data-record-id="${_escapeHtml(r.id)}">
                <div class="expertise-record-main">
                    <div class="expertise-record-title">${_escapeHtml(r.name || r.content.slice(0, 80))}</div>
                    <div class="expertise-record-meta">
                        <span>${_escapeHtml(r.type)}</span>
                        <span>${_escapeHtml(r.domain)}</span>
                        ${r.project ? `<span>${_escapeHtml(r.project)}</span>` : ''}
                        ${r.severity ? `<span>${_escapeHtml(r.severity)}</span>` : ''}
                    </div>
                    ${tagsHtml ? `<div class="expertise-record-tags">${tagsHtml}</div>` : ''}
                </div>
                <div class="expertise-record-confidence">${confidence}</div>
            </div>
        `;
    }).join('');

    return `
        <div class="expertise-record-list">${items}</div>
    `;
}

function _renderPagination(total, page) {
    const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    if (totalPages <= 1) return '';
    const start = page * PAGE_SIZE + 1;
    const end = Math.min((page + 1) * PAGE_SIZE, total);
    return `
        <div class="expertise-pagination">
            <button class="glass-btn" id="expertisePrevPage" ${page === 0 ? 'disabled' : ''}>Prev</button>
            <span class="expertise-pagination-info">${start}–${end} of ${total}</span>
            <button class="glass-btn" id="expertiseNextPage" ${page >= totalPages - 1 ? 'disabled' : ''}>Next</button>
        </div>
    `;
}

function _renderRecordDetail(record, lineage) {
    const tagsHtml = (record.tags || []).map(t => `<span class="expertise-tag">${_escapeHtml(t)}</span>`).join('');

    const conversationLinks = (lineage?.conversations || []).map(cid =>
        `<li><a href="/conversation/${encodeURIComponent(cid)}">${_escapeHtml(cid)}</a></li>`
    ).join('');

    const derivedList = (lineage?.derived_records || []).map(rid =>
        `<li>${_escapeHtml(rid)}</li>`
    ).join('');

    return `
        <div class="expertise-detail-panel" id="expertiseDetailPanel">
            <div class="expertise-detail-header">
                <h3>${_escapeHtml(record.name || record.type)}</h3>
                <button class="expertise-detail-close" id="expertiseDetailClose" aria-label="Close">&#x2715;</button>
            </div>
            <div class="expertise-detail-meta-grid">
                <div class="expertise-detail-field">
                    <span class="expertise-detail-field-label">Type</span>
                    <span class="expertise-detail-field-value">${_escapeHtml(record.type)}</span>
                </div>
                <div class="expertise-detail-field">
                    <span class="expertise-detail-field-label">Domain</span>
                    <span class="expertise-detail-field-value">${_escapeHtml(record.domain)}</span>
                </div>
                ${record.project ? `
                <div class="expertise-detail-field">
                    <span class="expertise-detail-field-label">Project</span>
                    <span class="expertise-detail-field-value">${_escapeHtml(record.project)}</span>
                </div>` : ''}
                ${record.severity ? `
                <div class="expertise-detail-field">
                    <span class="expertise-detail-field-label">Severity</span>
                    <span class="expertise-detail-field-value">${_escapeHtml(record.severity)}</span>
                </div>` : ''}
                <div class="expertise-detail-field">
                    <span class="expertise-detail-field-label">Confidence</span>
                    <span class="expertise-detail-field-value">${record.confidence != null ? Math.round(record.confidence * 100) + '%' : '—'}</span>
                </div>
                <div class="expertise-detail-field">
                    <span class="expertise-detail-field-label">Validations</span>
                    <span class="expertise-detail-field-value">${record.validation_count ?? 0}</span>
                </div>
                <div class="expertise-detail-field">
                    <span class="expertise-detail-field-label">Status</span>
                    <span class="expertise-detail-field-value">${record.is_active ? 'Active' : 'Inactive'}</span>
                </div>
                <div class="expertise-detail-field">
                    <span class="expertise-detail-field-label">Created</span>
                    <span class="expertise-detail-field-value">${record.created_at ? new Date(record.created_at).toLocaleDateString() : '—'}</span>
                </div>
            </div>
            <div class="expertise-detail-content">${_escapeHtml(record.content)}</div>
            ${record.example ? `<div class="expertise-detail-field"><span class="expertise-detail-field-label">Example</span><div class="expertise-detail-content" style="margin-top:4px;">${_escapeHtml(record.example)}</div></div>` : ''}
            ${record.rationale ? `<div class="expertise-detail-field"><span class="expertise-detail-field-label">Rationale</span><div class="expertise-detail-content" style="margin-top:4px;">${_escapeHtml(record.rationale)}</div></div>` : ''}
            ${tagsHtml ? `<div class="expertise-record-tags">${tagsHtml}</div>` : ''}
            ${record.source_conversation_id ? `
                <div class="expertise-detail-provenance">
                    <span>Source:</span>
                    <a href="/conversation/${encodeURIComponent(record.source_conversation_id)}">${_escapeHtml(record.source_conversation_id)}</a>
                    ${record.source_agent ? `<span>via ${_escapeHtml(record.source_agent)}</span>` : ''}
                </div>` : ''}
            ${(conversationLinks || derivedList) ? `
                <div class="expertise-detail-lineage">
                    <h4>Lineage</h4>
                    ${conversationLinks ? `
                        <p style="font-size:11px;color:hsl(var(--text-tertiary));margin:0 0 6px;">Source Conversations</p>
                        <ul class="expertise-lineage-list">${conversationLinks}</ul>` : ''}
                    ${derivedList ? `
                        <p style="font-size:11px;color:hsl(var(--text-tertiary));margin:8px 0 6px;">Derived Records</p>
                        <ul class="expertise-lineage-list">${derivedList}</ul>` : ''}
                </div>` : ''}
        </div>
    `;
}

// ── Tab rendering ────────────────────────────────────────────────────────────

async function _renderDomainsTab(container) {
    container.innerHTML = '<div class="expertise-loading">Loading domain status...</div>';
    try {
        const status = await _fetchStatus();
        container.innerHTML = _renderStatsRow(status) + _renderDomainTable(status);

        // Click on domain row to filter records tab
        container.querySelectorAll('.expertise-table tbody tr').forEach(row => {
            row.addEventListener('click', () => {
                _state.filters.domain = row.dataset.domain || '';
                _state.page = 0;
                _switchTab(document.getElementById('results'), 'records');
            });
        });
    } catch (err) {
        container.innerHTML = `<div class="expertise-error">${_escapeHtml(err.message)}</div>`;
    }
}

async function _renderRecordsTab(container) {
    container.innerHTML = '<div class="expertise-loading">Loading records...</div>';
    try {
        const [domainsData, recordsData] = await Promise.all([
            _fetchDomains(),
            _fetchRecords(_state.filters, _state.page * PAGE_SIZE),
        ]);

        const filterHtml = _renderFilterBar(domainsData);
        const listHtml = _renderRecordList(recordsData.results, recordsData.total);
        const paginationHtml = _renderPagination(recordsData.total, _state.page);
        const detailAreaId = 'expertiseDetailArea';

        container.innerHTML = filterHtml + listHtml + paginationHtml + `<div id="${detailAreaId}"></div>`;

        // Pre-fill filter values from state
        const domainSel = container.querySelector('#expertiseDomainFilter');
        if (domainSel) domainSel.value = _state.filters.domain;
        const typeSel = container.querySelector('#expertiseTypeFilter');
        if (typeSel) typeSel.value = _state.filters.type;
        const sevSel = container.querySelector('#expertiseSeverityFilter');
        if (sevSel) sevSel.value = _state.filters.severity;

        // Apply filter button
        const applyBtn = container.querySelector('#expertiseApplyFilters');
        if (applyBtn) {
            applyBtn.addEventListener('click', () => {
                _state.filters.q = container.querySelector('#expertiseSearch')?.value?.trim() || '';
                _state.filters.type = container.querySelector('#expertiseTypeFilter')?.value || '';
                _state.filters.domain = container.querySelector('#expertiseDomainFilter')?.value || '';
                _state.filters.severity = container.querySelector('#expertiseSeverityFilter')?.value || '';
                _state.filters.active_only = container.querySelector('#expertiseActiveOnly')?.checked ?? true;
                _state.page = 0;
                _renderRecordsTab(container);
            });
        }

        // Enter key in search field
        const searchInput = container.querySelector('#expertiseSearch');
        if (searchInput) {
            searchInput.addEventListener('keypress', e => {
                if (e.key === 'Enter') applyBtn?.click();
            });
        }

        // Record click
        container.querySelectorAll('.expertise-record-item').forEach(item => {
            item.addEventListener('click', async () => {
                const recordId = item.dataset.recordId;
                if (!recordId) return;
                _state.selectedRecordId = recordId;
                container.querySelectorAll('.expertise-record-item').forEach(i => i.classList.remove('selected'));
                item.classList.add('selected');
                const detailArea = container.querySelector(`#${detailAreaId}`);
                if (!detailArea) return;
                detailArea.innerHTML = '<div class="expertise-loading">Loading record...</div>';
                try {
                    const [record, lineage] = await Promise.all([
                        _fetchRecord(recordId),
                        _fetchLineage(recordId).catch(() => null),
                    ]);
                    detailArea.innerHTML = _renderRecordDetail(record, lineage);
                    detailArea.querySelector('#expertiseDetailClose')?.addEventListener('click', () => {
                        detailArea.innerHTML = '';
                        _state.selectedRecordId = null;
                        item.classList.remove('selected');
                    });
                    detailArea.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                } catch (err) {
                    detailArea.innerHTML = `<div class="expertise-error">${_escapeHtml(err.message)}</div>`;
                }
            });
        });

        // Pagination
        container.querySelector('#expertisePrevPage')?.addEventListener('click', () => {
            if (_state.page > 0) { _state.page--; _renderRecordsTab(container); }
        });
        container.querySelector('#expertiseNextPage')?.addEventListener('click', () => {
            const totalPages = Math.ceil(recordsData.total / PAGE_SIZE);
            if (_state.page < totalPages - 1) { _state.page++; _renderRecordsTab(container); }
        });
    } catch (err) {
        container.innerHTML = `<div class="expertise-error">${_escapeHtml(err.message)}</div>`;
    }
}

// ── Tab switching ────────────────────────────────────────────────────────────

function _switchTab(resultsDiv, tabName) {
    _state.activeTab = tabName;
    // Update tab button states
    resultsDiv.querySelectorAll('.expertise-tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });
    // Update panel visibility
    resultsDiv.querySelectorAll('.expertise-tab-panel').forEach(panel => {
        panel.classList.toggle('active', panel.dataset.panel === tabName);
    });
    // Render content
    const panel = resultsDiv.querySelector(`.expertise-tab-panel[data-panel="${tabName}"]`);
    if (!panel) return;
    if (tabName === 'domains') _renderDomainsTab(panel);
    else if (tabName === 'records') _renderRecordsTab(panel);
}

// ── Public entry point ───────────────────────────────────────────────────────

export async function showExpertise() {
    const resultsDiv = document.getElementById('results');
    if (!resultsDiv) return;
    _hideSearchUi();

    resultsDiv.innerHTML = `
        <div class="expertise-view">
            <div class="expertise-header">
                <div>
                    <h2>Expertise</h2>
                    <p>Browse and manage extracted knowledge records.</p>
                </div>
                <div class="expertise-header-actions">
                    <button class="glass-btn" data-action="back" id="expertiseBackBtn">&#x2190; Back to Search</button>
                </div>
            </div>
            <div class="expertise-tabs">
                <button class="expertise-tab-btn active" data-tab="domains">Domain Health</button>
                <button class="expertise-tab-btn" data-tab="records">Records</button>
            </div>
            <div class="expertise-tab-panel active" data-panel="domains"></div>
            <div class="expertise-tab-panel" data-panel="records"></div>
        </div>
    `;

    // Tab button listeners
    resultsDiv.querySelectorAll('.expertise-tab-btn').forEach(btn => {
        btn.addEventListener('click', () => _switchTab(resultsDiv, btn.dataset.tab));
    });

    // Back button
    resultsDiv.querySelector('#expertiseBackBtn')?.addEventListener('click', async () => {
        _showSearchUi();
        showSearchView();
        const restored = await restoreSearchState();
        if (!restored) {
            sessionStorage.removeItem('lastView');
            showSearchView();
        }
    });

    // Render initial tab
    const initialTab = _state.activeTab || 'domains';
    _switchTab(resultsDiv, initialTab);
}
