// Contradiction Resolution Module

import { showSearchView } from './search.js';
import { restoreSearchState } from './session.js';

let _state = {
    selectedEdgeId: null,
    recordA: null,
    recordB: null,
    pendingStrategy: null,
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
    sessionStorage.setItem('lastView', 'contradictions');
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

async function _apiPost(url, body) {
    const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail || `Request failed: ${response.status}`);
    }
    return response.json();
}

async function _fetchContradictions(unresolvedOnly = true) {
    const params = new URLSearchParams({ unresolved_only: String(unresolvedOnly) });
    return _apiFetch(`/api/knowledge-graph/contradictions?${params.toString()}`);
}

async function _fetchRecord(recordId) {
    return _apiFetch(`/api/expertise/${encodeURIComponent(recordId)}`);
}

async function _fetchGraphStats() {
    return _apiFetch('/api/knowledge-graph/stats');
}

async function _resolveContradiction(edgeId, strategy, params) {
    return _apiPost('/api/knowledge-graph/resolve', { edge_id: edgeId, strategy, params });
}

// ── Renderers ────────────────────────────────────────────────────────────────

function _renderGraphStats(stats) {
    const healthPct = Math.round((stats.health_score ?? 0) * 100);
    const healthColor = healthPct >= 80 ? 'var(--success)' : healthPct >= 50 ? 'var(--warning)' : 'var(--danger)';

    return `
        <div class="kg-stats-row">
            <div class="expertise-stat-card">
                <span class="expertise-stat-label">Nodes</span>
                <span class="expertise-stat-value">${stats.node_count ?? 0}</span>
            </div>
            <div class="expertise-stat-card">
                <span class="expertise-stat-label">Edges</span>
                <span class="expertise-stat-value">${stats.edge_count ?? 0}</span>
            </div>
            <div class="expertise-stat-card">
                <span class="expertise-stat-label">Contradictions</span>
                <span class="expertise-stat-value" style="color:hsl(var(--danger))">${stats.contradiction_count ?? 0}</span>
            </div>
            <div class="expertise-stat-card">
                <span class="expertise-stat-label">Unresolved</span>
                <span class="expertise-stat-value" style="color:hsl(var(--warning))">${stats.unresolved_contradiction_count ?? 0}</span>
            </div>
            <div class="expertise-stat-card">
                <span class="expertise-stat-label">Health</span>
                <span class="expertise-stat-value" style="color:hsl(${healthColor})">${healthPct}%</span>
                <div class="kg-health-bar">
                    <div class="kg-health-bar-fill" style="width:${healthPct}%;background:hsl(${healthColor})"></div>
                </div>
            </div>
        </div>
    `;
}

function _renderContradictionList(contradictions) {
    if (!contradictions.length) {
        return `
            <div class="contradiction-all-resolved">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                All contradictions resolved.
            </div>
        `;
    }

    const items = contradictions.map(c => `
        <div class="contradiction-item" data-edge-id="${_escapeHtml(c.edge_id)}" data-record-a="${_escapeHtml(c.record_id_a)}" data-record-b="${_escapeHtml(c.record_id_b)}">
            <div>
                <div class="contradiction-item-ids">${_escapeHtml(c.record_id_a.slice(0, 8))} &#x21C4; ${_escapeHtml(c.record_id_b.slice(0, 8))}</div>
                <div class="contradiction-item-meta">${new Date(c.created_at).toLocaleDateString()}</div>
            </div>
            <button class="glass-btn" style="font-size:11px;padding:4px 10px;" data-resolve-edge="${_escapeHtml(c.edge_id)}">Resolve</button>
        </div>
    `).join('');

    return `<div class="contradiction-list">${items}</div>`;
}

function _renderRecordCard(record, label, isWinner = false) {
    return `
        <div class="contradiction-record-card ${isWinner ? 'winner' : ''}" data-record-card="${_escapeHtml(record.id)}">
            <h4>${_escapeHtml(label)}: ${_escapeHtml(record.id.slice(0, 8))}</h4>
            <div class="contradiction-record-content">${_escapeHtml(record.content)}</div>
            <div class="contradiction-record-meta">
                <span><strong>Type:</strong> ${_escapeHtml(record.type)}</span>
                <span><strong>Domain:</strong> ${_escapeHtml(record.domain)}</span>
                ${record.project ? `<span><strong>Project:</strong> ${_escapeHtml(record.project)}</span>` : ''}
                <span><strong>Confidence:</strong> ${record.confidence != null ? Math.round(record.confidence * 100) + '%' : '—'}</span>
            </div>
        </div>
    `;
}

function _renderResolutionPanel(edgeId, recordA, recordB) {
    return `
        <div class="contradiction-actions" id="contradictionActions">
            <h4>Resolve Contradiction</h4>
            <div class="contradiction-action-row" id="contradictionActionButtons">
                <button class="glass-btn" data-strategy="supersede" data-winner="${_escapeHtml(recordA.id)}">A Supersedes B</button>
                <button class="glass-btn" data-strategy="supersede" data-winner="${_escapeHtml(recordB.id)}">B Supersedes A</button>
                <button class="glass-btn" data-strategy="scope_both">Scope Both</button>
                <button class="glass-btn" data-strategy="merge">Merge</button>
                <button class="glass-btn" data-strategy="dismiss">Dismiss</button>
                <button class="glass-btn" data-strategy="keep_both">Keep Both</button>
            </div>

            <div class="contradiction-scope-input" id="contradictionScopeInput">
                <label style="font-size:11px;color:hsl(var(--text-tertiary));">Scope for Record A</label>
                <input type="text" id="scopeA" placeholder="e.g. applies only to production" />
                <label style="font-size:11px;color:hsl(var(--text-tertiary));">Scope for Record B</label>
                <input type="text" id="scopeB" placeholder="e.g. applies only to staging" />
                <button class="glass-btn glass-btn-primary" id="confirmScope">Confirm Scope</button>
            </div>

            <div class="contradiction-merge-input" id="contradictionMergeInput">
                <label style="font-size:11px;color:hsl(var(--text-tertiary));">Merged content</label>
                <textarea id="mergedContent" rows="3" placeholder="Enter merged knowledge content..."></textarea>
                <button class="glass-btn glass-btn-primary" id="confirmMerge">Confirm Merge</button>
            </div>

            <div class="contradiction-dismiss-input" id="contradictionDismissInput">
                <label style="font-size:11px;color:hsl(var(--text-tertiary));">Reason for dismissal</label>
                <input type="text" id="dismissReason" placeholder="e.g. false positive, context mismatch" />
                <button class="glass-btn glass-btn-primary" id="confirmDismiss">Confirm Dismiss</button>
            </div>

            <div class="contradiction-dismiss-input" id="contradictionKeepBothInput">
                <label style="font-size:11px;color:hsl(var(--text-tertiary));">Reason to keep both</label>
                <input type="text" id="keepBothReason" placeholder="e.g. different contexts, both valid" />
                <button class="glass-btn glass-btn-primary" id="confirmKeepBoth">Confirm Keep Both</button>
            </div>

            <div class="contradiction-status" id="contradictionStatus"></div>
        </div>
    `;
}

// ── Event wiring for resolution panel ───────────────────────────────────────

function _wireResolutionPanel(container, edgeId, recordA, recordB, onResolved) {
    const status = container.querySelector('#contradictionStatus');
    const scopeInput = container.querySelector('#contradictionScopeInput');
    const mergeInput = container.querySelector('#contradictionMergeInput');
    const dismissInput = container.querySelector('#contradictionDismissInput');
    const keepBothInput = container.querySelector('#contradictionKeepBothInput');

    function _clearInputs() {
        [scopeInput, mergeInput, dismissInput, keepBothInput].forEach(el => {
            if (el) el.classList.remove('visible');
        });
    }

    container.querySelectorAll('[data-strategy]').forEach(btn => {
        btn.addEventListener('click', async () => {
            const strategy = btn.dataset.strategy;
            _clearInputs();
            status.textContent = '';
            status.className = 'contradiction-status';

            if (strategy === 'supersede') {
                const winnerId = btn.dataset.winner;
                try {
                    await _resolveContradiction(edgeId, 'supersede', { winner_id: winnerId });
                    status.textContent = 'Resolved: supersede applied.';
                    status.classList.add('success');
                    onResolved();
                } catch (err) {
                    status.textContent = err.message;
                    status.classList.add('error');
                }
            } else if (strategy === 'scope_both') {
                scopeInput.classList.add('visible');
            } else if (strategy === 'merge') {
                mergeInput.classList.add('visible');
            } else if (strategy === 'dismiss') {
                dismissInput.classList.add('visible');
            } else if (strategy === 'keep_both') {
                keepBothInput.classList.add('visible');
            }
        });
    });

    container.querySelector('#confirmScope')?.addEventListener('click', async () => {
        const scopeA = container.querySelector('#scopeA')?.value?.trim();
        const scopeB = container.querySelector('#scopeB')?.value?.trim();
        if (!scopeA || !scopeB) { status.textContent = 'Both scope fields required.'; status.classList.add('error'); return; }
        try {
            await _resolveContradiction(edgeId, 'scope_both', { scope_a: scopeA, scope_b: scopeB });
            status.textContent = 'Resolved: scopes applied.';
            status.classList.add('success');
            onResolved();
        } catch (err) {
            status.textContent = err.message;
            status.classList.add('error');
        }
    });

    container.querySelector('#confirmMerge')?.addEventListener('click', async () => {
        const merged = container.querySelector('#mergedContent')?.value?.trim();
        if (!merged) { status.textContent = 'Merged content required.'; status.classList.add('error'); return; }
        try {
            await _resolveContradiction(edgeId, 'merge', { merged_content: merged });
            status.textContent = 'Resolved: records merged.';
            status.classList.add('success');
            onResolved();
        } catch (err) {
            status.textContent = err.message;
            status.classList.add('error');
        }
    });

    container.querySelector('#confirmDismiss')?.addEventListener('click', async () => {
        const reason = container.querySelector('#dismissReason')?.value?.trim();
        if (!reason) { status.textContent = 'Dismiss reason required.'; status.classList.add('error'); return; }
        try {
            await _resolveContradiction(edgeId, 'dismiss', { reason });
            status.textContent = 'Resolved: contradiction dismissed.';
            status.classList.add('success');
            onResolved();
        } catch (err) {
            status.textContent = err.message;
            status.classList.add('error');
        }
    });

    container.querySelector('#confirmKeepBoth')?.addEventListener('click', async () => {
        const reason = container.querySelector('#keepBothReason')?.value?.trim();
        if (!reason) { status.textContent = 'Reason required.'; status.classList.add('error'); return; }
        try {
            await _resolveContradiction(edgeId, 'keep_both', { reason });
            status.textContent = 'Resolved: both records kept.';
            status.classList.add('success');
            onResolved();
        } catch (err) {
            status.textContent = err.message;
            status.classList.add('error');
        }
    });
}

// ── Main render ──────────────────────────────────────────────────────────────

async function _renderContradictionsView(container, unresolvedOnly = true) {
    container.innerHTML = '<div class="expertise-loading">Loading contradictions...</div>';
    try {
        const [statsData, contradictionsData] = await Promise.all([
            _fetchGraphStats(),
            _fetchContradictions(unresolvedOnly),
        ]);

        const statsHtml = _renderGraphStats(statsData);
        const listHtml = _renderContradictionList(contradictionsData.results || []);

        container.innerHTML = `
            ${statsHtml}
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;flex-wrap:wrap;gap:8px;">
                <h3 style="margin:0;font-size:15px;font-weight:600;">
                    ${unresolvedOnly ? 'Unresolved' : 'All'} Contradictions
                    <span style="font-size:12px;font-weight:400;color:hsl(var(--text-tertiary));margin-left:8px;">${contradictionsData.total ?? 0} found</span>
                </h3>
                <label style="display:flex;align-items:center;gap:6px;font-size:12px;color:hsl(var(--text-tertiary));">
                    <input type="checkbox" id="contradictionUnresolvedOnly" ${unresolvedOnly ? 'checked' : ''} />
                    Unresolved only
                </label>
            </div>
            ${listHtml}
            <div id="contradictionDetailArea"></div>
        `;

        // Toggle unresolved filter
        container.querySelector('#contradictionUnresolvedOnly')?.addEventListener('change', e => {
            _renderContradictionsView(container, e.target.checked);
        });

        // Click contradiction item to open detail
        container.querySelectorAll('.contradiction-item').forEach(item => {
            item.addEventListener('click', async (e) => {
                if (e.target.dataset.resolveEdge || e.target.closest('[data-resolve-edge]')) return;
                _openContradictionDetail(container, item);
            });
        });

        // Resolve button shortcut
        container.querySelectorAll('[data-resolve-edge]').forEach(btn => {
            btn.addEventListener('click', async () => {
                const item = btn.closest('.contradiction-item');
                if (item) _openContradictionDetail(container, item);
            });
        });
    } catch (err) {
        container.innerHTML = `<div class="expertise-error">${_escapeHtml(err.message)}</div>`;
    }
}

async function _openContradictionDetail(container, item) {
    const edgeId = item.dataset.edgeId;
    const recordIdA = item.dataset.recordA;
    const recordIdB = item.dataset.recordB;
    if (!edgeId) return;

    container.querySelectorAll('.contradiction-item').forEach(i => i.classList.remove('selected'));
    item.classList.add('selected');

    const detailArea = container.querySelector('#contradictionDetailArea');
    if (!detailArea) return;
    detailArea.innerHTML = '<div class="expertise-loading">Loading records...</div>';

    try {
        const [recA, recB] = await Promise.all([
            _fetchRecord(recordIdA),
            _fetchRecord(recordIdB),
        ]);
        _state.recordA = recA;
        _state.recordB = recB;
        _state.selectedEdgeId = edgeId;

        detailArea.innerHTML = `
            <div style="margin-top:16px;">
                <div class="contradiction-comparison">
                    ${_renderRecordCard(recA, 'Record A')}
                    ${_renderRecordCard(recB, 'Record B')}
                </div>
                <div style="margin-top:12px;">
                    ${_renderResolutionPanel(edgeId, recA, recB)}
                </div>
            </div>
        `;

        const unresolvedOnly = container.querySelector('#contradictionUnresolvedOnly')?.checked ?? true;
        _wireResolutionPanel(detailArea, edgeId, recA, recB, () => {
            // After resolution, refresh the list
            setTimeout(() => _renderContradictionsView(container, unresolvedOnly), 800);
        });

        detailArea.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    } catch (err) {
        detailArea.innerHTML = `<div class="expertise-error">${_escapeHtml(err.message)}</div>`;
    }
}

// ── Public entry point ───────────────────────────────────────────────────────

export async function showContradictions() {
    const resultsDiv = document.getElementById('results');
    if (!resultsDiv) return;
    _hideSearchUi();

    resultsDiv.innerHTML = `
        <div class="expertise-view">
            <div class="expertise-header">
                <div>
                    <h2>Knowledge Graph</h2>
                    <p>Detect and resolve contradictions between expertise records.</p>
                </div>
                <div class="expertise-header-actions">
                    <button class="glass-btn" id="contradictionsBackBtn">&#x2190; Back to Search</button>
                </div>
            </div>
            <div id="contradictionsBody"></div>
        </div>
    `;

    resultsDiv.querySelector('#contradictionsBackBtn')?.addEventListener('click', async () => {
        _showSearchUi();
        showSearchView();
        const restored = await restoreSearchState();
        if (!restored) {
            sessionStorage.removeItem('lastView');
            showSearchView();
        }
    });

    const body = resultsDiv.querySelector('#contradictionsBody');
    if (body) await _renderContradictionsView(body, true);
}
