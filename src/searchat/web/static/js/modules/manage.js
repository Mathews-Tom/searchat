function escapeHtml(value) {
    const div = document.createElement('div');
    div.textContent = value == null ? '' : String(value);
    return div.innerHTML;
}

function formatDate(value) {
    if (!value) return '';
    try {
        return new Date(value).toLocaleDateString();
    } catch (_error) {
        return String(value).slice(0, 10);
    }
}

function detectTool(conversation) {
    if (conversation.tool) return conversation.tool;

    const filePath = String(conversation.file_path || '').toLowerCase();
    if (filePath.includes('vibe')) return 'vibe';
    if (filePath.includes('claude')) return 'claude';
    if (filePath.includes('codex')) return 'codex';
    if (filePath.includes('gemini')) return 'gemini';
    if (filePath.includes('cursor')) return 'cursor';
    return '';
}

function createManagePageController() {
    const selected = new Set();
    const overlay = document.getElementById('confirmOverlay');
    const msgEl = document.getElementById('confirmMessage');
    const okBtn = document.getElementById('confirmOk');
    const cancelBtn = document.getElementById('confirmCancel');
    const list = document.getElementById('manage-list');
    const toolbar = document.getElementById('manageToolbar');
    const countEl = document.getElementById('manageSelectionCount');
    const previewPanel = document.getElementById('previewPanel');
    const previewOverlay = document.getElementById('previewOverlay');
    const previewContent = document.getElementById('previewContent');
    const deleteBtn = document.getElementById('manageDeleteBtn');
    const deleteSourceCheckbox = document.getElementById('deleteSourceFiles');
    const page = {
        state: {
            page: 1,
            pageSize: 50,
            totalPages: 0,
        },
    };

    function updateToolbar() {
        if (!toolbar || !countEl) return;
        if (selected.size > 0) {
            toolbar.style.display = 'flex';
            countEl.textContent = `${selected.size} selected`;
        } else {
            toolbar.style.display = 'none';
        }
    }

    function openPreviewPanel() {
        if (!previewPanel || !previewOverlay) return;
        previewPanel.classList.add('open');
        previewOverlay.classList.add('open');
        document.body.style.overflow = 'hidden';
    }

    function closePreviewPanel() {
        if (!previewPanel || !previewOverlay) return;
        previewPanel.classList.remove('open');
        previewOverlay.classList.remove('open');
        document.body.style.overflow = '';
    }

    function renderPreviewContent(conversation) {
        if (!conversation || typeof conversation !== 'object') {
            return '<div class="preview-error"><p>Conversation not found.</p></div>';
        }

        const messages = Array.isArray(conversation.messages) ? conversation.messages : [];
        const previewMessages = messages.slice(0, 10);
        const remaining = Math.max(messages.length - previewMessages.length, 0);
        const tool = detectTool(conversation);

        let html = '<div class="preview-header">';
        html += `<h3 class="preview-title">${escapeHtml(conversation.title || 'Untitled Conversation')}</h3>`;
        html += '<div class="preview-meta">';
        if (conversation.project_id) {
            html += `<span>${escapeHtml(conversation.project_id)}</span>`;
        }
        if (conversation.message_count) {
            html += `<span>${escapeHtml(conversation.message_count)} messages</span>`;
        }
        if (conversation.created_at) {
            html += `<span>${escapeHtml(String(conversation.created_at).slice(0, 10))}</span>`;
        }
        if (tool) {
            html += `<span class="manage-tool-badge manage-tool-${escapeHtml(tool)}">${escapeHtml(tool)}</span>`;
        }
        html += '</div></div>';

        html += '<div class="preview-messages">';
        previewMessages.forEach((message) => {
            const role = escapeHtml((message && message.role) || 'unknown');
            const content = escapeHtml((message && message.content) || '');
            html += `<div class="preview-message preview-role-${role}">`;
            html += `<div class="preview-message-role">${role}</div>`;
            html += `<div class="preview-message-content">${content}</div>`;
            html += '</div>';
        });

        if (remaining > 0) {
            html += `<div class="preview-truncated">&hellip; ${remaining} more message${remaining !== 1 ? 's' : ''} not shown</div>`;
        }
        html += '</div>';

        return html;
    }

    function renderManageList(data) {
        if (!list) return;

        const results = Array.isArray(data.results) ? data.results : [];
        const total = Number(data.total || 0);
        page.state.totalPages = total > 0 ? Math.ceil(total / page.state.pageSize) : 0;

        if (!results.length) {
            list.innerHTML = '<div class="result" style="padding: 48px; text-align: center;"><p style="color: hsl(var(--text-tertiary)); margin: 0;">No conversations found.</p></div>';
            updateToolbar();
            return;
        }

        let html = `<div class="results-header">${total} conversation${total !== 1 ? 's' : ''}`;
        if (page.state.page > 1) {
            html += ` &middot; Page ${page.state.page} of ${page.state.totalPages}`;
        }
        html += '</div>';

        results.forEach((conversation) => {
            const checked = selected.has(conversation.conversation_id) ? ' checked' : '';
            const filePath = String(conversation.file_path || '');
            html += `
<div class="result manage-result" id="manage-${escapeHtml(conversation.conversation_id)}">
    <label class="manage-checkbox">
        <input type="checkbox" name="cid" value="${escapeHtml(conversation.conversation_id)}"${checked}>
        <span class="manage-checkmark"></span>
    </label>
    <div class="manage-result-content">
        <div class="result-title">${escapeHtml(conversation.title || 'Untitled')}</div>
        <div class="result-meta">
            <span>${escapeHtml(conversation.project_id || '')}</span>
            ${conversation.message_count ? `<span>&middot; ${escapeHtml(conversation.message_count)} messages</span>` : ''}
            ${conversation.updated_at ? `<span>&middot; ${escapeHtml(formatDate(conversation.updated_at))}</span>` : ''}
            ${conversation.tool ? `<span class="manage-tool-badge manage-tool-${escapeHtml(conversation.tool)}">${escapeHtml(conversation.tool)}</span>` : ''}
        </div>
        ${filePath ? `<div class="manage-source-path" title="${escapeHtml(filePath)}">${escapeHtml(filePath)}</div>` : ''}
    </div>
    <button class="glass-btn manage-preview-btn" title="Preview conversation" data-conversation-id="${escapeHtml(conversation.conversation_id)}">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
        </svg>
    </button>
</div>`;
        });

        if (page.state.totalPages > 1) {
            html += '<div class="manage-pagination">';
            if (page.state.page > 1) {
                html += '<button class="glass-btn" data-manage-page="prev">&larr; Previous</button>';
            }
            html += `<span class="manage-page-info">Page ${page.state.page} of ${page.state.totalPages}</span>`;
            if (page.state.page < page.state.totalPages) {
                html += '<button class="glass-btn" data-manage-page="next">Next &rarr;</button>';
            }
            html += '</div>';
        }

        list.innerHTML = html;
        updateToolbar();
    }

    function loadManageConversations() {
        if (!list) return Promise.resolve();

        list.innerHTML = '<div style="text-align: center; padding: 48px;"><span class="spinner" id="manageSpinner" style="display: inline-block;"></span><p style="color: hsl(var(--text-tertiary));">Loading conversations...</p></div>';

        const params = new URLSearchParams({
            sort_by: document.getElementById('manageSortBy').value,
            limit: String(page.state.pageSize),
            offset: String((page.state.page - 1) * page.state.pageSize),
        });

        const project = document.getElementById('manageProject').value;
        const tool = document.getElementById('manageTool').value;
        if (project) params.set('project', project);
        if (tool) params.set('tool', tool);

        return fetch(`/api/conversations/all?${params.toString()}`)
            .then((response) => {
                if (!response.ok) throw new Error('Failed to load conversations');
                return response.json();
            })
            .then((data) => {
                renderManageList(data);
            })
            .catch((error) => {
                list.innerHTML = `<div class="result" style="padding: 48px; text-align: center;"><p style="color: hsl(var(--danger)); margin: 0;">${escapeHtml(error.message)}</p></div>`;
            });
    }

    function loadManageProjects() {
        const projectSelect = document.getElementById('manageProject');
        if (!projectSelect) return Promise.resolve();

        return fetch('/api/projects/summary')
            .then((response) => {
                if (!response.ok) return [];
                return response.json();
            })
            .then((projects) => {
                if (!Array.isArray(projects)) return;

                const currentValue = projectSelect.value;
                projectSelect.innerHTML = '<option value="">All Projects</option>';
                projects.forEach((project) => {
                    const option = document.createElement('option');
                    option.value = project.project_id;
                    option.textContent = `${project.project_id} (${project.conversation_count})`;
                    projectSelect.appendChild(option);
                });
                if (currentValue) {
                    projectSelect.value = currentValue;
                }
            })
            .catch(() => null);
    }

    function performDelete(ids, deleteSource) {
        if (!deleteBtn) return;

        deleteBtn.disabled = true;
        deleteBtn.textContent = 'Deleting...';

        fetch('/api/conversations/delete', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                conversation_ids: ids,
                delete_source_files: deleteSource,
            }),
        })
            .then((response) => {
                if (!response.ok) throw new Error(`Delete failed: ${response.status}`);
                return response.json();
            })
            .then((result) => {
                selected.clear();
                updateToolbar();
                loadManageConversations();

                const notification = document.createElement('div');
                notification.className = 'manage-notification glass';
                notification.innerHTML = `<strong>Deleted ${result.deleted} conversation${result.deleted > 1 ? 's' : ''}.</strong>`
                    + ` Removed ${result.removed_vectors} vectors.`
                    + (result.source_files_deleted > 0
                        ? ` Deleted ${result.source_files_deleted} source file${result.source_files_deleted > 1 ? 's' : ''}.`
                        : '');
                document.querySelector('.manage-page').insertBefore(notification, list);
                setTimeout(() => notification.remove(), 8000);
            })
            .catch((error) => {
                alert(`Delete failed: ${error.message}`);
            })
            .finally(() => {
                deleteBtn.disabled = false;
                deleteBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg> Delete Selected';
            });
    }

    function requestDeleteSelected() {
        if (!overlay || !msgEl || !okBtn || !cancelBtn || selected.size === 0) return;

        const deleteSource = Boolean(deleteSourceCheckbox && deleteSourceCheckbox.checked);
        const count = selected.size;
        const label = `${count} conversation${count > 1 ? 's' : ''}`;
        let message = `Remove ${label} from the search index?`;
        if (deleteSource) {
            message += '\n\nThe original source files (e.g. ~/.claude/projects/.../*.jsonl) will also be permanently deleted from disk.';
        }

        msgEl.textContent = message;
        overlay.classList.add('active');
        overlay.setAttribute('aria-hidden', 'false');

        let onOk;
        let onCancel;
        let onEsc;

        const cleanup = () => {
            okBtn.removeEventListener('click', onOk);
            cancelBtn.removeEventListener('click', onCancel);
            document.removeEventListener('keydown', onEsc);
            overlay.classList.remove('active');
            overlay.setAttribute('aria-hidden', 'true');
        };

        onOk = () => {
            cleanup();
            performDelete(Array.from(selected), deleteSource);
        };
        onCancel = () => cleanup();
        onEsc = (event) => {
            if (event.key === 'Escape') cleanup();
        };

        okBtn.addEventListener('click', onOk);
        cancelBtn.addEventListener('click', onCancel);
        document.addEventListener('keydown', onEsc);
    }

    function bindListEvents() {
        if (!list) return;

        list.addEventListener('change', (event) => {
            if (!event.target.matches('.manage-checkbox input[type="checkbox"]')) return;
            const conversationId = event.target.value;
            if (event.target.checked) {
                selected.add(conversationId);
            } else {
                selected.delete(conversationId);
            }
            updateToolbar();
        });

        list.addEventListener('click', (event) => {
            const previewButton = event.target.closest('.manage-preview-btn');
            if (previewButton) {
                const conversationId = previewButton.dataset.conversationId;
                if (!conversationId || !previewContent) return;

                openPreviewPanel();
                previewContent.innerHTML = '<div style="text-align: center; padding: 48px;"><span class="spinner" id="previewSpinner" style="display: inline-block;"></span></div>';

                fetch(`/api/conversation/${encodeURIComponent(conversationId)}`)
                    .then((response) => {
                        if (!response.ok) throw new Error('Failed to load preview');
                        return response.json();
                    })
                    .then((conversation) => {
                        previewContent.innerHTML = renderPreviewContent(conversation);
                    })
                    .catch((error) => {
                        previewContent.innerHTML = `<div style="padding: 24px; color: hsl(var(--danger));">${escapeHtml(error.message)}</div>`;
                    });
                return;
            }

            const pageButton = event.target.closest('[data-manage-page]');
            if (!pageButton) return;

            if (pageButton.dataset.managePage === 'prev' && page.state.page > 1) {
                page.state.page -= 1;
            } else if (pageButton.dataset.managePage === 'next' && page.state.page < page.state.totalPages) {
                page.state.page += 1;
            }
            loadManageConversations();
        });
    }

    function bindControls() {
        const filterIds = ['manageProject', 'manageTool', 'manageSortBy'];
        filterIds.forEach((id) => {
            const element = document.getElementById(id);
            if (!element) return;
            element.addEventListener('change', () => {
                page.state.page = 1;
                loadManageConversations();
            });
        });

        document.getElementById('manageSelectAllButton')?.addEventListener('click', () => {
            document.querySelectorAll('#manage-list .manage-checkbox input[type="checkbox"]').forEach((checkbox) => {
                checkbox.checked = true;
                selected.add(checkbox.value);
            });
            updateToolbar();
        });

        document.getElementById('manageDeselectAllButton')?.addEventListener('click', () => {
            document.querySelectorAll('#manage-list .manage-checkbox input[type="checkbox"]').forEach((checkbox) => {
                checkbox.checked = false;
            });
            selected.clear();
            updateToolbar();
        });

        deleteBtn?.addEventListener('click', requestDeleteSelected);
        previewOverlay?.addEventListener('click', closePreviewPanel);
        document.getElementById('previewCloseButton')?.addEventListener('click', closePreviewPanel);
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && previewPanel?.classList.contains('open')) {
                closePreviewPanel();
            }
        });
    }

    return {
        init() {
            bindListEvents();
            bindControls();
            loadManageProjects().finally(loadManageConversations);
        },
    };
}

export function initManagePage() {
    if (!document.getElementById('manage-list')) return;
    const controller = createManagePageController();
    controller.init();
}
