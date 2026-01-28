// Search Functionality

import { saveAllConversationsState, saveSearchState, restoreSearchState } from './session.js';
import { addToHistory } from './search-history.js';
import { loadCodeBlocks } from './code-extraction.js';
import { createStarIcon } from './bookmarks.js';
import { loadSimilarConversations } from './similar.js';
import { addCheckboxToResult } from './bulk-export.js';

let _searchNonce = 0;

function _sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

export async function search() {
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

    const resultsDiv = document.getElementById('results');
    resultsDiv.innerHTML = '<div class="loading">Searching...</div>';

    const params = new URLSearchParams({
        q: query || '*',  // Use wildcard if no query
        mode: document.getElementById('mode').value,
        project: document.getElementById('project').value,
        tool: tool,
        date: document.getElementById('date').value,
        sort_by: document.getElementById('sortBy').value
    });

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
        }
    }

    const response = await fetch(`/api/search?${params}`);

    if (response.status === 503) {
        const payload = await response.json();
        if (payload && payload.status === 'warming') {
            const delay = payload.retry_after_ms || 500;
            resultsDiv.innerHTML = '<div class="loading">Warming up search engine (first run)...</div>';
            await _sleep(delay);
            if (nonce === _searchNonce) {
                return search();
            }
            return;
        }

        const msg = payload && payload.detail
            ? payload.detail
            : (payload && payload.errors ? JSON.stringify(payload.errors) : 'Search warming failed');
        resultsDiv.innerHTML = `<div style="color: #f44336;">${msg}</div>`;
        return;
    }

    if (!response.ok) {
        const payload = await response.json().catch(() => null);
        const msg = payload && payload.detail ? payload.detail : (payload && payload.errors ? JSON.stringify(payload.errors) : 'Search failed');
        resultsDiv.innerHTML = `<div style="color: #f44336;">${msg}</div>`;
        return;
    }

    const data = await response.json();

    resultsDiv.innerHTML = '';
    if (data.results.length === 0) {
        resultsDiv.innerHTML = '<div>No results found</div>';
        saveSearchState();
        return;
    }

    resultsDiv.innerHTML = `<div class="results-header">Found ${data.total} results in ${Math.round(data.search_time_ms)}ms</div>`;

    data.results.forEach((r, index) => {
        const div = document.createElement('div');
        const isWSL = r.source === 'WSL';
        div.className = `result ${isWSL ? 'wsl' : 'windows'}`;
        div.id = `result-${index}`;
        div.dataset.conversationId = r.conversation_id;
        // Get last segment of conversation ID
        const shortId = r.conversation_id.split('-').pop();

        // Detect tool from API field
        let tool = r.tool || 'claude';
        let toolLabel = tool === 'opencode' ? 'OpenCode' : (tool === 'vibe' ? 'Vibe' : 'Claude Code');

        div.innerHTML = `
            <div class="result-title">${r.title}</div>
            <div class="result-meta">
                <span class="tool-badge ${tool}">${toolLabel}</span> •
                <span class="conv-id">...${shortId}</span> •
                ${r.project_id} •
                ${r.message_count} msgs •
                ${new Date(r.updated_at).toLocaleDateString()}
            </div>
            <div class="result-snippet">${r.snippet}</div>
            <div class="result-actions">
                <button class="resume-btn" data-conversation-id="${r.conversation_id}">
                    ⚡ Resume Session
                </button>
            </div>
        `;

        // Add checkbox if bulk mode is active
        addCheckboxToResult(div, r.conversation_id);

        // Add star icon to title
        const titleDiv = div.querySelector('.result-title');
        const starIcon = createStarIcon(r.conversation_id);
        titleDiv.appendChild(starIcon);

        // Add click handler for resume button
        const resumeBtn = div.querySelector('.resume-btn');
        resumeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            resumeSession(r.conversation_id, resumeBtn);
        });

        div.onclick = () => {
            saveSearchState();
            sessionStorage.setItem('lastScrollPosition', window.scrollY);
            sessionStorage.setItem('lastResultIndex', index);
            sessionStorage.setItem('activeConversationId', r.conversation_id);
            loadConversationView(r.conversation_id);
        };
        resultsDiv.appendChild(div);
    });

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
            let toolLabel = tool === 'opencode' ? 'OpenCode' : (tool === 'vibe' ? 'Vibe' : 'Claude Code');

            div.innerHTML = `
                <div class="result-title">${r.title}</div>
                <div class="result-meta">
                    <span class="tool-badge ${tool}">${toolLabel}</span> •
                    <span class="conv-id">...${shortId}</span> •
                    ${r.project_id} •
                    ${r.message_count} msgs •
                    ${new Date(r.updated_at).toLocaleDateString()}
                </div>
                <div class="result-snippet">${r.snippet}</div>
                <div class="result-actions">
                    <button class="resume-btn" data-conversation-id="${r.conversation_id}">
                        ⚡ Resume Session
                    </button>
                </div>
            `;

            // Add checkbox if bulk mode is active
            addCheckboxToResult(div, r.conversation_id);

            // Add star icon to title
            const titleDiv = div.querySelector('.result-title');
            const starIcon = createStarIcon(r.conversation_id);
            titleDiv.appendChild(starIcon);

            // Add click handler for resume button
            const resumeBtn = div.querySelector('.resume-btn');
            resumeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                resumeSession(r.conversation_id, resumeBtn);
            });

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
        const response = await fetch(`/api/conversation/${conversationId}`);
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
        const tool = data.tool || (data.file_path.endsWith('.jsonl') ? 'claude' : 'vibe');
        const toolLabel = tool === 'opencode' ? 'OpenCode' : (tool === 'vibe' ? 'Vibe' : 'Claude Code');
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
        resumeBtn.textContent = '⚡ Resume Session';
        resumeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            resumeSession(data.conversation_id, resumeBtn);
        });

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
    link.href = `/api/conversation/${conversationId}/export?format=${format}`;
    link.download = `conversation-${conversationId}.${format === 'markdown' ? 'md' : format}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}
