// Search Functionality

import { saveAllConversationsState, saveSearchState, restoreSearchState } from './session.js';
import { addToHistory } from './search-history.js';
import { loadCodeBlocks } from './code-extraction.js';
import { createStarIcon } from './bookmarks.js';
import { loadSimilarConversations } from './similar.js';
import { addCheckboxToResult } from './bulk-export.js';
import { renderPagination, setTotalResults, getOffset, resetPagination } from './pagination.js';
import { getProjectSummaries } from './api.js';
import { applySnapshotParam, isSnapshotActive, getSnapshotName } from './dataset.js';

let _searchNonce = 0;
const _snippetCodeMap = new Map();
let _snippetCodeCounter = 0;
let _resultsHandlersBound = false;

function findProjectSuggestion(query) {
    const summaries = getProjectSummaries();
    if (!Array.isArray(summaries) || summaries.length === 0) return null;

    const trimmed = query.trim().toLowerCase();
    if (trimmed.length < 3) return null;

    const tokens = tokenizeQuery(trimmed);
    if (tokens.length === 0) return null;

    let bestMatch = null;
    let bestScore = 0;

    for (const summary of summaries) {
        const projectId = String(summary.project_id || '').toLowerCase();
        if (!projectId) continue;

        if (trimmed.includes(projectId)) {
            if (projectId.length > bestScore) {
                bestScore = projectId.length;
                bestMatch = summary;
            }
            continue;
        }

        for (const token of tokens) {
            if (projectId.includes(token) && token.length > bestScore) {
                bestScore = token.length;
                bestMatch = summary;
            }
        }
    }

    return bestMatch;
}

function tokenizeQuery(value) {
    const tokens = [];
    const parts = value.split(/[^a-z0-9_-]+/);
    for (const part of parts) {
        if (part.length >= 3) {
            tokens.push(part);
        }
    }
    return tokens;
}

export function initProjectSuggestion() {
    const searchBox = document.getElementById('search');
    const suggestion = document.getElementById('projectSuggestion');
    const projectSelect = document.getElementById('project');
    if (!searchBox || !suggestion || !projectSelect) return;

    function hideSuggestion() {
        suggestion.style.display = 'none';
        suggestion.innerHTML = '';
    }

    function updateSuggestion() {
        const match = findProjectSuggestion(searchBox.value);
        if (!match) {
            hideSuggestion();
            return;
        }

        if (projectSelect.value === match.project_id) {
            hideSuggestion();
            return;
        }

        suggestion.style.display = 'flex';
        suggestion.innerHTML = `
            <span>Search within <strong>${escapeHtml(match.project_id)}</strong>?</span>
            <button type="button" data-project-id="${escapeHtml(match.project_id)}">Scope to project</button>
        `;
    }

    function handleInput() {
        updateSuggestion();
    }

    function handleProjectChange() {
        updateSuggestion();
    }

    function handleSuggestionClick(event) {
        const button = event.target.closest('button');
        if (!button) return;
        const projectId = button.dataset.projectId;
        if (!projectId) return;
        projectSelect.value = projectId;
        hideSuggestion();
        if (window.search) window.search();
    }

    searchBox.addEventListener('input', handleInput);
    projectSelect.addEventListener('change', handleProjectChange);
    suggestion.addEventListener('click', handleSuggestionClick);

    updateSuggestion();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getToolLabel(tool) {
    if (tool === 'opencode') {
        return 'OpenCode';
    }
    if (tool === 'vibe') {
        return 'Vibe';
    }
    if (tool === 'codex') {
        return 'Codex';
    }
    if (tool === 'gemini') {
        return 'Gemini CLI';
    }
    if (tool === 'continue') {
        return 'Continue';
    }
    if (tool === 'cursor') {
        return 'Cursor';
    }
    if (tool === 'aider') {
        return 'Aider';
    }
    return 'Claude Code';
}

function detectToolFromPath(filePath) {
    const normalized = String(filePath || '').toLowerCase().replace(/\\/g, '/');
    if (normalized.includes('/.local/share/opencode/')) return 'opencode';
    if (normalized.includes('/.codex/')) return 'codex';
    if (normalized.includes('/.continue/sessions/') && normalized.endsWith('.json')) return 'continue';
    if (normalized.includes('.vscdb.cursor/') && normalized.endsWith('.json')) return 'cursor';
    if (normalized.includes('/.gemini/tmp/') && normalized.includes('/chats/') && normalized.endsWith('.json')) return 'gemini';
    if (normalized.endsWith('/.aider.chat.history.md') || normalized.endsWith('.aider.chat.history.md')) return 'aider';
    if (normalized.includes('/.claude/') && normalized.endsWith('.jsonl')) return 'claude';
    if (normalized.includes('/.vibe/') && normalized.endsWith('.json')) return 'vibe';
    if (normalized.endsWith('.jsonl')) return 'claude';
    return 'vibe';
}

function escapeRegExp(value) {
    return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function resolveErrorMessage(payload, fallback) {
    if (payload && payload.detail) {
        return payload.detail;
    }
    if (payload && payload.errors) {
        return JSON.stringify(payload.errors);
    }
    return fallback;
}

function normalizeHighlightTerms(terms) {
    if (!Array.isArray(terms)) return [];
    const normalized = [];
    for (const term of terms) {
        if (typeof term !== 'string') continue;
        const trimmed = term.trim();
        if (trimmed.length > 1) {
            normalized.push(trimmed);
        }
    }
    return normalized;
}

function highlightText(text, query, semanticTerms) {
    if (!text) return '';
    let output = escapeHtml(text);

    const trimmedQuery = (query || '').trim();
    if (trimmedQuery.length >= 2 && trimmedQuery !== '*') {
        const exactRegex = new RegExp(`(${escapeRegExp(trimmedQuery)})`, 'gi');
        output = output.replace(exactRegex, '<mark class="mark-exact">$1</mark>');
    }

    const terms = normalizeHighlightTerms(semanticTerms);
    for (const term of terms) {
        if (!term || term.toLowerCase() === trimmedQuery.toLowerCase()) continue;
        const termRegex = new RegExp(`(${escapeRegExp(term)})`, 'gi');
        output = output.replace(termRegex, '<mark class="mark-semantic">$1</mark>');
    }

    return output;
}

function renderCodeBlock(code, language) {
    const codeId = `snippet-code-${_snippetCodeCounter++}`;
    _snippetCodeMap.set(codeId, code);

    const escaped = escapeHtml(code);
    const lineCount = code.split('\n').length;
    const isCollapsed = lineCount > 30;

    return {
        html: `
            <div class="snippet-code-block" data-code-id="${codeId}" data-collapsed="${isCollapsed}">
                <div class="snippet-code-header">
                    <span class="snippet-code-lang">${escapeHtml(language || 'plaintext')}</span>
                    <span class="snippet-code-lines">${lineCount} lines</span>
                    <div class="snippet-code-actions">
                        <button class="snippet-copy" data-code-id="${codeId}">Copy</button>
                        ${isCollapsed ? '<button class="snippet-toggle">Expand</button>' : ''}
                    </div>
                </div>
                <pre class="snippet-code ${isCollapsed ? 'collapsed' : ''}"><code>${escaped}</code></pre>
            </div>
        `,
        collapsed: isCollapsed,
    };
}

function formatSnippet(snippet, query, semanticTerms) {
    if (!snippet) return '';
    const codePattern = /```(\w+)?\n([\s\S]*?)```/g;
    let lastIndex = 0;
    let match;
    let html = '';

    while ((match = codePattern.exec(snippet)) !== null) {
        const before = snippet.slice(lastIndex, match.index);
        if (before) {
            html += `<div class="snippet-text">${highlightText(before, query, semanticTerms)}</div>`;
        }

        const language = match[1] || 'plaintext';
        const code = match[2] || '';
        const rendered = renderCodeBlock(code.trim(), language);
        html += rendered.html;
        lastIndex = match.index + match[0].length;
    }

    const after = snippet.slice(lastIndex);
    if (after) {
        html += `<div class="snippet-text">${highlightText(after, query, semanticTerms)}</div>`;
    }

    if (!html) {
        html = `<div class="snippet-text">${highlightText(snippet, query, semanticTerms)}</div>`;
    }

    return html;
}

function renderDiffPreview(payload) {
    const summary = payload.summary || { added: 0, removed: 0, unchanged: 0 };
    const added = payload.added || [];
    const removed = payload.removed || [];
    const unchanged = payload.unchanged || [];

    return `
        <div class="diff-summary">
            <span class="diff-count added">+${summary.added}</span>
            <span class="diff-count removed">-${summary.removed}</span>
            <span class="diff-count unchanged">${summary.unchanged} unchanged</span>
        </div>
        <div class="diff-section">
            <div class="diff-title">Added</div>
            <pre class="diff-block diff-added">${escapeHtml(added.join('\n'))}</pre>
        </div>
        <div class="diff-section">
            <div class="diff-title">Removed</div>
            <pre class="diff-block diff-removed">${escapeHtml(removed.join('\n'))}</pre>
        </div>
        <details class="diff-section">
            <summary class="diff-title">Unchanged</summary>
            <pre class="diff-block diff-unchanged">${escapeHtml(unchanged.join('\n'))}</pre>
        </details>
    `;
}

function ensureResultsHandlers(resultsDiv) {
    if (_resultsHandlersBound) return;
    async function handleResultsClick(event) {
        const target = event.target;

        if (target.classList.contains('snippet-copy')) {
            event.stopPropagation();
            const codeId = target.dataset.codeId;
            const code = _snippetCodeMap.get(codeId) || '';
            if (!code) return;
            try {
                await navigator.clipboard.writeText(code);
                const original = target.textContent;
                target.textContent = 'Copied';
                setTimeout(function () {
                    target.textContent = original;
                }, 1500);
            } catch (error) {
                console.error('Failed to copy snippet code:', error);
            }
            return;
        }

        if (target.classList.contains('snippet-toggle')) {
            event.stopPropagation();
            const block = target.closest('.snippet-code-block');
            if (!block) return;
            const pre = block.querySelector('.snippet-code');
            if (!pre) return;
            const isCollapsed = pre.classList.contains('collapsed');
            pre.classList.toggle('collapsed');
            target.textContent = isCollapsed ? 'Collapse' : 'Expand';
            return;
        }

        if (target.classList.contains('diff-btn')) {
            event.stopPropagation();
            const resultCard = target.closest('.result');
            if (!resultCard) return;
            const diffContainer = resultCard.querySelector('.result-diff');
            if (!diffContainer) return;

            const isOpen = diffContainer.classList.toggle('open');
            if (!isOpen) {
                return;
            }

            if (diffContainer.dataset.loaded === 'true') {
                return;
            }

            const conversationId = resultCard.dataset.conversationId;
            const sourceStart = resultCard.dataset.messageStart;
            const sourceEnd = resultCard.dataset.messageEnd;
            const params = new URLSearchParams();
            if (sourceStart) params.append('source_start', sourceStart);
            if (sourceEnd) params.append('source_end', sourceEnd);
            applySnapshotParam(params);

            diffContainer.innerHTML = '<div class="loading">Loading diff...</div>';
            try {
                const response = await fetch(`/api/conversation/${conversationId}/diff?${params.toString()}`);
                if (!response.ok) {
                    const payload = await response.json().catch(() => null);
                    const msg = payload && payload.detail ? payload.detail : 'Failed to load diff';
                    diffContainer.innerHTML = `<div class="diff-error">${msg}</div>`;
                    return;
                }
                const payload = await response.json();
                diffContainer.innerHTML = renderDiffPreview(payload);
                diffContainer.dataset.loaded = 'true';
            } catch (error) {
                diffContainer.innerHTML = `<div class="diff-error">Error: ${error.message}</div>`;
            }
        }
    }

    resultsDiv.addEventListener('click', handleResultsClick);
    _resultsHandlersBound = true;
}

function _sleep(ms) {
    return new Promise(function (resolve) {
        setTimeout(resolve, ms);
    });
}

export async function search(resetPage = true, attempt = 0) {
    _searchNonce += 1;
    const nonce = _searchNonce;

    const query = document.getElementById('search').value;
    const project = document.getElementById('project').value;
    const tool = document.getElementById('tool').value;
    const date = document.getElementById('date').value;

    // Allow search if query OR any filter is set
    if (!query && !project && !tool && !date) {
        document.getElementById('results').innerHTML = '<div>Enter a search query or select a filter</div>';
        return;
    }

    // Reset to page 1 when starting a new search (not pagination)
    if (resetPage) {
        resetPagination();
    }

    const resultsDiv = document.getElementById('results');
    resultsDiv.innerHTML = '<div class="loading">Searching...</div>';
    _snippetCodeMap.clear();
    _snippetCodeCounter = 0;

    const params = new URLSearchParams({
        q: query || '*',  // Use wildcard if no query
        mode: document.getElementById('mode').value,
        project: document.getElementById('project').value,
        tool: tool,
        date: document.getElementById('date').value,
        sort_by: document.getElementById('sortBy').value,
        offset: getOffset()
    });

    const highlightProvider = document.getElementById('chatProvider')?.value;
    const highlightModel = document.getElementById('chatModel')?.value;
    const highlightToggle = document.getElementById('semanticHighlights');
    const shouldHighlight = highlightToggle?.checked
        && query.trim().length >= 4
        && document.getElementById('mode').value !== 'keyword';
    if (shouldHighlight && highlightProvider) {
        params.append('highlight', 'true');
        params.append('highlight_provider', highlightProvider);
        if (highlightModel) params.append('highlight_model', highlightModel);
    }

    // Add custom date range if selected
    if (document.getElementById('date').value === 'custom') {
        const dateFrom = document.getElementById('dateFrom').value;
        const dateTo = document.getElementById('dateTo').value;
        if (dateFrom) params.append('date_from', dateFrom);
        if (dateTo) params.append('date_to', dateTo);
    }

    const projectValue = document.getElementById('project').value;
    if (!tool) {
        if (projectValue.startsWith('opencode-')) {
            params.append('tool', 'opencode');
        } else if (projectValue.startsWith('vibe-')) {
            params.append('tool', 'vibe');
        } else if (projectValue === 'codex') {
            params.append('tool', 'codex');
        } else if (projectValue === 'gemini' || projectValue.startsWith('gemini-')) {
            params.append('tool', 'gemini');
        } else if (projectValue === 'continue' || projectValue.startsWith('continue-')) {
            params.append('tool', 'continue');
        } else if (projectValue === 'cursor' || projectValue.startsWith('cursor-')) {
            params.append('tool', 'cursor');
        } else if (projectValue === 'aider' || projectValue.startsWith('aider-')) {
            params.append('tool', 'aider');
        }
    }

    applySnapshotParam(params);

    const response = await fetch(`/api/search?${params}`);

    if (response.status === 503) {
        const payload = await response.json();
        if (payload && payload.status === 'warming') {
            const baseDelay = payload.retry_after_ms || 500;
            const delay = Math.min(baseDelay * Math.pow(2, attempt), 5000);
            if (attempt >= 6) {
                const details = payload.errors ? JSON.stringify(payload.errors) : 'No warmup details available.';
                resultsDiv.innerHTML = `
                    <div style="color: #f44336; margin-bottom: 8px;">Search warmup is taking too long.</div>
                    <div style="font-size: 12px; color: #888; margin-bottom: 10px;">${details}</div>
                    <button id="fallbackKeyword" style="background: #2196F3; padding: 6px 10px; border: none; border-radius: 6px; color: white; cursor: pointer;">Switch to Keyword Mode</button>
                `;
                const button = document.getElementById('fallbackKeyword');
                if (button) {
                    button.addEventListener('click', function () {
                        document.getElementById('mode').value = 'keyword';
                        return search();
                    });
                }
                return;
            }

            resultsDiv.innerHTML = `<div class="loading">Warming up search engine (first run)... retrying in ${Math.round(delay / 100) / 10}s</div>`;
            await _sleep(delay);
            if (nonce === _searchNonce) {
                return search(false, attempt + 1);
            }
            return;
        }

        const msg = resolveErrorMessage(payload, 'Search warming failed');
        resultsDiv.innerHTML = `<div style="color: #f44336;">${msg}</div>`;
        return;
    }

    if (!response.ok) {
        const payload = await response.json().catch(() => null);
        const msg = resolveErrorMessage(payload, 'Search failed');
        resultsDiv.innerHTML = `<div style="color: #f44336;">${msg}</div>`;
        return;
    }

    const data = await response.json();

    // Store total results for pagination
    setTotalResults(data.total);

    resultsDiv.innerHTML = '';
    if (data.results.length === 0) {
        resultsDiv.innerHTML = '<div>No results found</div>';
        saveSearchState();
        return;
    }

    const highlightTerms = Array.isArray(data.highlight_terms) ? data.highlight_terms : [];

    const paginationInfo = data.total > 20 ? ` (page ${Math.floor(getOffset() / 20) + 1})` : '';
    resultsDiv.innerHTML = `<div class="results-header">Found ${data.total} results in ${Math.round(data.search_time_ms)}ms${paginationInfo}</div>`;

    data.results.forEach((r, index) => {
        const div = document.createElement('div');
        const isWSL = r.source === 'WSL';
        div.className = `result ${isWSL ? 'wsl' : 'windows'}`;
        div.id = `result-${index}`;
        div.dataset.conversationId = r.conversation_id;
        if (typeof r.message_start_index === 'number') {
            div.dataset.messageStart = String(r.message_start_index);
        }
        if (typeof r.message_end_index === 'number') {
            div.dataset.messageEnd = String(r.message_end_index);
        }
        // Get last segment of conversation ID
        const shortId = r.conversation_id.split('-').pop();

        // Detect tool from API field
        let tool = r.tool || 'claude';
        const toolLabel = getToolLabel(tool);

        const highlightedTitle = highlightText(r.title, query, highlightTerms);
        const formattedSnippet = formatSnippet(r.snippet, query, highlightTerms);

        const snapshotName = getSnapshotName();
        const resumeButtonHtml = snapshotName
            ? `<button class="resume-btn" data-conversation-id="${r.conversation_id}" disabled title="Disabled in snapshot mode (${escapeHtml(snapshotName)})">⚡ Resume (disabled)</button>`
            : `<button class="resume-btn" data-conversation-id="${r.conversation_id}">⚡ Resume Session</button>`;

        div.innerHTML = `
            <div class="result-title">${highlightedTitle}</div>
            <div class="result-meta">
                <span class="tool-badge ${tool}">${toolLabel}</span> •
                <span class="conv-id">...${shortId}</span> •
                ${r.project_id} •
                ${r.message_count} msgs •
                ${new Date(r.updated_at).toLocaleDateString()}
            </div>
            <div class="result-snippet">${formattedSnippet}</div>
            <div class="result-actions">
                ${resumeButtonHtml}
                <button class="diff-btn" data-conversation-id="${r.conversation_id}">
                    View Diff
                </button>
            </div>
            <div class="result-diff" data-loaded="false"></div>
        `;

        // Add checkbox if bulk mode is active
        addCheckboxToResult(div, r.conversation_id);

        // Add star icon to title
        const titleDiv = div.querySelector('.result-title');
        const starIcon = createStarIcon(r.conversation_id);
        titleDiv.appendChild(starIcon);

        // Add click handler for resume button
        const resumeBtn = div.querySelector('.resume-btn');
        if (resumeBtn && !isSnapshotActive()) {
            resumeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                resumeSession(r.conversation_id, resumeBtn);
            });
        }

        div.onclick = () => {
            saveSearchState();
            sessionStorage.setItem('lastScrollPosition', window.scrollY);
            sessionStorage.setItem('lastResultIndex', index);
            sessionStorage.setItem('activeConversationId', r.conversation_id);
            loadConversationView(r.conversation_id);
        };
        resultsDiv.appendChild(div);
    });

    // Render pagination controls
    renderPagination(resultsDiv, search);

    ensureResultsHandlers(resultsDiv);

    // Add search to history
    addToHistory({
        query: query,
        mode: document.getElementById('mode').value,
        project: document.getElementById('project').value,
        tool: tool,
        date: document.getElementById('date').value,
        dateFrom: document.getElementById('date').value === 'custom' ? document.getElementById('dateFrom').value : '',
        dateTo: document.getElementById('date').value === 'custom' ? document.getElementById('dateTo').value : '',
        sortBy: document.getElementById('sortBy').value
    });

    saveSearchState();
}

export function showSearchView() {
    const header = document.getElementById('conversationHeader');
    const heroTitle = document.getElementById('heroTitle');
    const heroSubtitle = document.getElementById('heroSubtitle');
    const filters = document.getElementById('filters');
    const chatPanel = document.getElementById('chatPanel');
    const resultsDiv = document.getElementById('results');

    if (header) header.style.display = 'none';
    if (heroTitle) heroTitle.style.display = 'block';
    if (heroSubtitle) heroSubtitle.style.display = 'block';
    if (filters) filters.style.display = 'block';
    if (chatPanel) chatPanel.style.display = 'block';

    sessionStorage.removeItem('activeConversationId');

    if (resultsDiv) {
        resultsDiv.innerHTML = '';
        const lastView = sessionStorage.getItem('lastView');
        const hasSearchState = Boolean(sessionStorage.getItem('searchState'));
        const hasAllState = Boolean(sessionStorage.getItem('allConversationsState'));
        if (lastView || hasSearchState || hasAllState) {
            resultsDiv.innerHTML = '<div class="loading">Restoring results...</div>';
        } else {
            resultsDiv.innerHTML = '<div>Enter a search query or select a filter</div>';
        }
    }
}

export function toggleCustomDate() {
    const dateSelect = document.getElementById('date');
    const customRange = document.getElementById('customDateRange');
    customRange.style.display = dateSelect.value === 'custom' ? 'inline' : 'none';
}

export async function resumeSession(conversationId, buttonElement) {
    if (isSnapshotActive()) {
        console.error('Resume is disabled in snapshot mode');
        return;
    }
    const originalText = buttonElement.innerHTML;
    buttonElement.innerHTML = '⏳ Opening...';
    buttonElement.disabled = true;

    try {
        const response = await fetch('/api/resume', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ conversation_id: conversationId })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            buttonElement.innerHTML = '✓ Opened in terminal';
            buttonElement.classList.add('success');
            setTimeout(() => {
                buttonElement.innerHTML = originalText;
                buttonElement.classList.remove('success');
                buttonElement.disabled = false;
            }, 2000);
        } else {
            throw new Error(data.detail || 'Failed to resume session');
        }
    } catch (error) {
        buttonElement.innerHTML = '❌ Failed - check console';
        buttonElement.classList.add('error');
        console.error('Resume error:', error);
        setTimeout(() => {
            buttonElement.innerHTML = originalText;
            buttonElement.classList.remove('error');
            buttonElement.disabled = false;
        }, 3000);
    }
}

export async function showAllConversations() {
    const resultsDiv = document.getElementById('results');
    resultsDiv.innerHTML = '<div class="loading">Loading all conversations...</div>';
    _snippetCodeMap.clear();
    _snippetCodeCounter = 0;

    const sortBy = document.getElementById('sortBy').value;
    const project = document.getElementById('project').value;
    const tool = document.getElementById('tool').value;
    const date = document.getElementById('date').value;

    // Map sort values to API parameters
    let apiSortBy = 'length';
    if (sortBy === 'date_newest') apiSortBy = 'date_newest';
    else if (sortBy === 'date_oldest') apiSortBy = 'date_oldest';
    else if (sortBy === 'messages') apiSortBy = 'length';

    const params = new URLSearchParams({ sort_by: apiSortBy });
    if (project) {
        params.append('project', project);
    }
    if (tool) {
        params.append('tool', tool);
    } else if (project) {
        if (project.startsWith('opencode-')) {
            params.append('tool', 'opencode');
        } else if (project.startsWith('vibe-')) {
            params.append('tool', 'vibe');
        }
    }
    if (params.has('project')) {
        const projectValue = params.get('project') || '';
        if (projectValue.startsWith('opencode-')) {
            params.append('tool', 'opencode');
        } else if (projectValue.startsWith('vibe-')) {
            params.append('tool', 'vibe');
        }
    }
    if (date) {
        params.append('date', date);

        // Add custom date range if selected
        if (date === 'custom') {
            const dateFrom = document.getElementById('dateFrom').value;
            const dateTo = document.getElementById('dateTo').value;
            if (dateFrom) params.append('date_from', dateFrom);
            if (dateTo) params.append('date_to', dateTo);
        }
    }

    applySnapshotParam(params);

    try {
        const response = await fetch(`/api/conversations/all?${params}`);
        const data = await response.json();

        resultsDiv.innerHTML = '';
        if (data.results.length === 0) {
            resultsDiv.innerHTML = '<div>No conversations found</div>';
            return;
        }

        const projectInfo = project ? ` in project "${project}"` : '';
        const dateLabels = {
            'today': 'from today',
            'week': 'from last 7 days',
            'month': 'from last 30 days',
            'custom': 'from custom date range'
        };
        const dateInfo = date ? ` ${dateLabels[date] || ''}` : '';
        resultsDiv.innerHTML = `<div class="results-header">Showing all ${data.total} conversations${projectInfo}${dateInfo} (sorted by ${apiSortBy})</div>`;

        data.results.forEach((r, index) => {
            const div = document.createElement('div');
            const isWSL = r.source === 'WSL';
            div.className = `result ${isWSL ? 'wsl' : 'windows'}`;
            div.id = `result-${index}`;
            div.dataset.conversationId = r.conversation_id;
            const shortId = r.conversation_id.split('-').pop();

            // Detect tool from API field
            let tool = r.tool || 'claude';
            const toolLabel = getToolLabel(tool);

            const formattedSnippet = formatSnippet(r.snippet, '', []);

            const snapshotName = getSnapshotName();
            const resumeButtonHtml = snapshotName
                ? `<button class="resume-btn" data-conversation-id="${r.conversation_id}" disabled title="Disabled in snapshot mode (${escapeHtml(snapshotName)})">⚡ Resume (disabled)</button>`
                : `<button class="resume-btn" data-conversation-id="${r.conversation_id}">⚡ Resume Session</button>`;

            div.innerHTML = `
                <div class="result-title">${escapeHtml(r.title)}</div>
                <div class="result-meta">
                    <span class="tool-badge ${tool}">${toolLabel}</span> •
                    <span class="conv-id">...${shortId}</span> •
                    ${r.project_id} •
                    ${r.message_count} msgs •
                    ${new Date(r.updated_at).toLocaleDateString()}
                </div>
                <div class="result-snippet">${formattedSnippet}</div>
                <div class="result-actions">
                    ${resumeButtonHtml}
                    <button class="diff-btn" data-conversation-id="${r.conversation_id}">
                        View Diff
                    </button>
                </div>
                <div class="result-diff" data-loaded="false"></div>
            `;

            // Add checkbox if bulk mode is active
            addCheckboxToResult(div, r.conversation_id);

            // Add star icon to title
            const titleDiv = div.querySelector('.result-title');
            const starIcon = createStarIcon(r.conversation_id);
            titleDiv.appendChild(starIcon);

            // Add click handler for resume button
            const resumeBtn = div.querySelector('.resume-btn');
            if (resumeBtn && !isSnapshotActive()) {
                resumeBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    resumeSession(r.conversation_id, resumeBtn);
                });
            }

            div.onclick = () => {
                saveAllConversationsState();
                sessionStorage.setItem('lastScrollPosition', window.scrollY);
                sessionStorage.setItem('lastResultIndex', index);
                sessionStorage.setItem('activeConversationId', r.conversation_id);
                loadConversationView(r.conversation_id);
            };
            resultsDiv.appendChild(div);
        });
        saveAllConversationsState();
        ensureResultsHandlers(resultsDiv);
    } catch (error) {
        resultsDiv.innerHTML = `<div style="color: #f44336;">Error: ${error.message}</div>`;
    }
}

export async function loadConversationView(conversationId, pushState = true) {
    if (!conversationId) {
        const cachedId = sessionStorage.getItem('activeConversationId');
        if (cachedId) {
            conversationId = cachedId;
        } else {
            return;
        }
    }
    const resultsDiv = document.getElementById('results');
    const header = document.getElementById('conversationHeader');
    const heroTitle = document.getElementById('heroTitle');
    const heroSubtitle = document.getElementById('heroSubtitle');
    const filters = document.getElementById('filters');
    const chatPanel = document.getElementById('chatPanel');

    if (header) header.style.display = 'block';
    if (heroTitle) heroTitle.style.display = 'none';
    if (heroSubtitle) heroSubtitle.style.display = 'none';
    if (filters) filters.style.display = 'none';
    if (chatPanel) chatPanel.style.display = 'none';

    const backButton = document.querySelector('#conversationHeader .back-button');
    if (backButton) {
        backButton.onclick = async (event) => {
            event.preventDefault();
            history.pushState({}, '', '/');
            showSearchView();
            await restoreSearchState();
        };
    }

    resultsDiv.innerHTML = '';
    const debug = document.createElement('div');
    debug.className = 'results-header';
    debug.textContent = `Loading conversation ${conversationId}...`;
    resultsDiv.appendChild(debug);

    const loading = document.createElement('div');
    loading.className = 'loading';
    loading.textContent = 'Loading conversation...';
    resultsDiv.appendChild(loading);

    try {
        if (pushState) {
            history.pushState({ conversationId }, '', `/conversation/${conversationId}`);
        }
        const params = applySnapshotParam(new URLSearchParams());
        const url = params.toString()
            ? `/api/conversation/${conversationId}?${params.toString()}`
            : `/api/conversation/${conversationId}`;
        const response = await fetch(url);
        if (!response.ok) {
            const payload = await response.json().catch(() => null);
            const msg = payload && payload.detail ? payload.detail : 'Failed to load conversation';
            resultsDiv.innerHTML = '';
            const errorDiv = document.createElement('div');
            errorDiv.style.color = '#f44336';
            errorDiv.textContent = msg;
            resultsDiv.appendChild(errorDiv);
            return;
        }

        const data = await response.json();
        debug.textContent = `Loaded ${conversationId} | messages: ${Array.isArray(data.messages) ? data.messages.length : 0}`;
        const tool = data.tool || detectToolFromPath(data.file_path);
        const toolLabel = getToolLabel(tool);
        const projectPath = data.project_path || '';
        const headerMeta = projectPath
            ? `Project: ${projectPath}`
            : `Project: ${data.project_id || 'Unknown'}`;

        resultsDiv.innerHTML = '';

        const headerDiv = document.createElement('div');
        headerDiv.className = 'header';

        const badge = document.createElement('span');
        badge.className = `tool-badge ${tool}`;
        badge.textContent = toolLabel;

        const title = document.createElement('h2');
        title.textContent = data.title || 'No title available';

        const meta = document.createElement('div');
        meta.textContent = `${headerMeta} | Messages: ${data.message_count || 0}`;

        const actions = document.createElement('div');
        actions.className = 'result-actions';

        const resumeBtn = document.createElement('button');
        resumeBtn.className = 'resume-btn';
        resumeBtn.dataset.conversationId = data.conversation_id;
        if (isSnapshotActive()) {
            resumeBtn.textContent = '⚡ Resume (disabled)';
            resumeBtn.disabled = true;
            resumeBtn.title = `Disabled in snapshot mode (${getSnapshotName()})`;
        } else {
            resumeBtn.textContent = '⚡ Resume Session';
            resumeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                resumeSession(data.conversation_id, resumeBtn);
            });
        }

        // Export button with dropdown
        const exportContainer = document.createElement('div');
        exportContainer.style.cssText = 'position: relative; display: inline-block;';

        const exportBtn = document.createElement('button');
        exportBtn.className = 'export-btn';
        exportBtn.textContent = '📥 Export';
        exportBtn.style.cssText = `
            background: var(--accent-primary);
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-family: 'Space Grotesk', sans-serif;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.2s;
        `;

        const exportDropdown = document.createElement('div');
        exportDropdown.style.cssText = `
            display: none;
            position: absolute;
            right: 0;
            top: 100%;
            margin-top: 4px;
            background: var(--bg-elevated);
            border: 1px solid var(--border-default);
            border-radius: 6px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            z-index: 1000;
            min-width: 150px;
        `;

        const formats = [
            { value: 'json', label: '📄 JSON', desc: 'Structured data' },
            { value: 'markdown', label: '📝 Markdown', desc: 'Formatted text' },
            { value: 'text', label: '📃 Plain Text', desc: 'Simple text' }
        ];

        formats.forEach(fmt => {
            const option = document.createElement('div');
            option.style.cssText = `
                padding: 10px 14px;
                cursor: pointer;
                transition: background 0.2s;
                border-bottom: 1px solid var(--border-muted);
            `;
            option.innerHTML = `
                <div style="font-weight: 500; color: var(--text-primary); margin-bottom: 2px;">
                    ${fmt.label}
                </div>
                <div style="font-size: 12px; color: var(--text-muted);">
                    ${fmt.desc}
                </div>
            `;

            option.addEventListener('mouseenter', () => {
                option.style.background = 'var(--bg-surface)';
            });
            option.addEventListener('mouseleave', () => {
                option.style.background = 'transparent';
            });
            option.addEventListener('click', () => {
                exportConversation(data.conversation_id, fmt.value);
                exportDropdown.style.display = 'none';
            });

            exportDropdown.appendChild(option);
        });

        // Remove border from last option
        exportDropdown.lastChild.style.borderBottom = 'none';

        exportBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            exportDropdown.style.display = exportDropdown.style.display === 'none' ? 'block' : 'none';
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!exportContainer.contains(e.target)) {
                exportDropdown.style.display = 'none';
            }
        });

        exportContainer.appendChild(exportBtn);
        exportContainer.appendChild(exportDropdown);

        actions.appendChild(resumeBtn);
        actions.appendChild(exportContainer);
        headerDiv.appendChild(badge);
        headerDiv.appendChild(title);
        headerDiv.appendChild(meta);
        headerDiv.appendChild(actions);
        resultsDiv.appendChild(headerDiv);

        // Add tabs for Messages and Code
        const tabsDiv = document.createElement('div');
        tabsDiv.className = 'conversation-tabs';
        tabsDiv.style.cssText = `
            display: flex;
            gap: 8px;
            margin: 20px 0 16px 0;
            border-bottom: 1px solid var(--border-default);
            padding-bottom: 0;
        `;

        const messagesTab = document.createElement('button');
        messagesTab.className = 'tab-button active';
        messagesTab.textContent = 'Messages';
        messagesTab.style.cssText = `
            padding: 10px 20px;
            background: transparent;
            border: none;
            border-bottom: 2px solid var(--accent-primary);
            color: var(--accent-primary);
            font-family: 'Space Grotesk', sans-serif;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        `;

        const codeTab = document.createElement('button');
        codeTab.className = 'tab-button';
        codeTab.textContent = 'Code';
        codeTab.style.cssText = `
            padding: 10px 20px;
            background: transparent;
            border: none;
            border-bottom: 2px solid transparent;
            color: var(--text-muted);
            font-family: 'Space Grotesk', sans-serif;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        `;

        const similarTab = document.createElement('button');
        similarTab.className = 'tab-button';
        similarTab.textContent = 'Similar';
        similarTab.style.cssText = `
            padding: 10px 20px;
            background: transparent;
            border: none;
            border-bottom: 2px solid transparent;
            color: var(--text-muted);
            font-family: 'Space Grotesk', sans-serif;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        `;

        // Tab content containers
        const messagesContainer = document.createElement('div');
        messagesContainer.id = 'messagesContainer';
        messagesContainer.style.display = 'block';

        const codeContainer = document.createElement('div');
        codeContainer.id = 'codeContainer';
        codeContainer.style.display = 'none';

        const similarContainer = document.createElement('div');
        similarContainer.id = 'similarContainer';
        similarContainer.style.display = 'none';

        // Helper function to switch tabs
        const switchTab = (activeTab, activeContainer) => {
            [messagesTab, codeTab, similarTab].forEach(tab => {
                tab.style.borderBottomColor = 'transparent';
                tab.style.color = 'var(--text-muted)';
            });
            [messagesContainer, codeContainer, similarContainer].forEach(container => {
                container.style.display = 'none';
            });

            activeTab.style.borderBottomColor = 'var(--accent-primary)';
            activeTab.style.color = 'var(--accent-primary)';
            activeContainer.style.display = 'block';
        };

        // Tab click handlers
        messagesTab.addEventListener('click', () => {
            switchTab(messagesTab, messagesContainer);
        });

        codeTab.addEventListener('click', () => {
            switchTab(codeTab, codeContainer);
            // Load code blocks if not already loaded
            if (!codeContainer.dataset.loaded) {
                loadCodeBlocks(conversationId, codeContainer);
                codeContainer.dataset.loaded = 'true';
            }
        });

        similarTab.addEventListener('click', () => {
            switchTab(similarTab, similarContainer);
            // Load similar conversations if not already loaded
            if (!similarContainer.dataset.loaded) {
                loadSimilarConversations(conversationId, similarContainer);
                similarContainer.dataset.loaded = 'true';
            }
        });

        tabsDiv.appendChild(messagesTab);
        tabsDiv.appendChild(codeTab);
        tabsDiv.appendChild(similarTab);
        resultsDiv.appendChild(tabsDiv);
        resultsDiv.appendChild(messagesContainer);
        resultsDiv.appendChild(codeContainer);
        resultsDiv.appendChild(similarContainer);

        if (data.messages && Array.isArray(data.messages) && data.messages.length > 0) {
            data.messages.forEach((msg, i) => {
                const msgDiv = document.createElement('div');
                msgDiv.className = `message ${msg.role || 'unknown'}`;

                const roleDiv = document.createElement('div');
                roleDiv.className = 'role';
                roleDiv.textContent = `${(msg.role || 'unknown').toUpperCase()} - Message ${i + 1}`;

                const contentDiv = document.createElement('div');
                contentDiv.className = 'content';
                contentDiv.textContent = msg.content || '';

                msgDiv.appendChild(roleDiv);
                msgDiv.appendChild(contentDiv);
                messagesContainer.appendChild(msgDiv);
            });
        } else {
            const empty = document.createElement('div');
            empty.className = 'message';
            empty.textContent = 'No messages available';
            messagesContainer.appendChild(empty);
        }

        sessionStorage.setItem('activeConversationId', conversationId);
    } catch (error) {
        resultsDiv.innerHTML = '';
        const errorDiv = document.createElement('div');
        errorDiv.style.color = '#f44336';
        errorDiv.textContent = `Error: ${error.message}`;
        resultsDiv.appendChild(errorDiv);
    }
}

/**
 * Export conversation in specified format
 */
function exportConversation(conversationId, format) {
    // Create a temporary link to trigger download
    const link = document.createElement('a');
    const params = new URLSearchParams({ format: format });
    applySnapshotParam(params);
    link.href = `/api/conversation/${conversationId}/export?${params.toString()}`;
    link.download = `conversation-${conversationId}.${format === 'markdown' ? 'md' : format}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}
