// Bulk export functionality

import { applySnapshotParam } from './dataset.js';

let selectedConversations = new Set();
let bulkModeActive = false;

/**
 * Initialize bulk export
 */
export function initBulkExport() {
    // Bulk export toolbar will be created dynamically when needed
}

/**
 * Toggle bulk selection mode
 */
export function toggleBulkMode() {
    bulkModeActive = !bulkModeActive;
    selectedConversations.clear();

    const resultsDiv = document.getElementById('results');
    const results = resultsDiv.querySelectorAll('.result');

    if (bulkModeActive) {
        // Show checkboxes
        results.forEach(result => {
            const checkbox = createCheckbox(result.dataset.conversationId);
            result.insertBefore(checkbox, result.firstChild);
        });

        showBulkToolbar();
    } else {
        // Hide checkboxes
        results.forEach(result => {
            const checkbox = result.querySelector('.bulk-checkbox');
            if (checkbox) {
                checkbox.remove();
            }
        });

        hideBulkToolbar();
    }

    updateToggleButton();
}

/**
 * Create checkbox for a conversation
 */
function createCheckbox(conversationId) {
    const container = document.createElement('div');
    container.className = 'bulk-checkbox';
    container.style.cssText = `
        float: left;
        margin-right: 12px;
        margin-top: 2px;
    `;

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.dataset.conversationId = conversationId;
    checkbox.style.cssText = `
        width: 18px;
        height: 18px;
        cursor: pointer;
        accent-color: hsl(var(--accent));
    `;

    checkbox.addEventListener('change', (e) => {
        e.stopPropagation();
        if (checkbox.checked) {
            selectedConversations.add(conversationId);
        } else {
            selectedConversations.delete(conversationId);
        }
        updateBulkToolbar();
    });

    container.appendChild(checkbox);
    return container;
}

/**
 * Show bulk actions toolbar
 */
function showBulkToolbar() {
    let toolbar = document.getElementById('bulkToolbar');
    if (!toolbar) {
        toolbar = document.createElement('div');
        toolbar.id = 'bulkToolbar';
        toolbar.className = 'glass-elevated';
        toolbar.style.cssText = `
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 1000;
            display: flex;
            align-items: center;
            gap: 16px;
        `;

        toolbar.innerHTML = `
            <span id="bulkCount" style="font-size: 14px; color: hsl(var(--text-primary)); font-weight: 500;">
                0 selected
            </span>
            <button id="bulkSelectAll" class="glass-btn">Select All</button>
            <button id="bulkDeselectAll" class="glass-btn">Deselect All</button>
            <div style="width: 1px; height: 24px; background: hsl(var(--border-glass));"></div>
            <button id="bulkExportJson" class="glass-btn glass-btn-primary">Export JSON</button>
            <button id="bulkExportMarkdown" class="glass-btn glass-btn-primary">Export Markdown</button>
            <button id="bulkExportText" class="glass-btn glass-btn-primary">Export Text</button>
        `;

        document.body.appendChild(toolbar);

        // Add event listeners
        document.getElementById('bulkSelectAll').addEventListener('click', selectAll);
        document.getElementById('bulkDeselectAll').addEventListener('click', deselectAll);
        document.getElementById('bulkExportJson').addEventListener('click', () => bulkExport('json'));
        document.getElementById('bulkExportMarkdown').addEventListener('click', () => bulkExport('markdown'));
        document.getElementById('bulkExportText').addEventListener('click', () => bulkExport('text'));
    }

    toolbar.style.display = 'flex';
}

/**
 * Hide bulk actions toolbar
 */
function hideBulkToolbar() {
    const toolbar = document.getElementById('bulkToolbar');
    if (toolbar) {
        toolbar.style.display = 'none';
    }
}

/**
 * Update bulk toolbar state
 */
function updateBulkToolbar() {
    const countSpan = document.getElementById('bulkCount');
    if (countSpan) {
        const count = selectedConversations.size;
        countSpan.textContent = `${count} selected`;
    }
}

/**
 * Select all visible conversations
 */
function selectAll() {
    const resultsDiv = document.getElementById('results');
    const checkboxes = resultsDiv.querySelectorAll('.bulk-checkbox input[type="checkbox"]');

    checkboxes.forEach(checkbox => {
        checkbox.checked = true;
        selectedConversations.add(checkbox.dataset.conversationId);
    });

    updateBulkToolbar();
}

/**
 * Deselect all conversations
 */
function deselectAll() {
    const resultsDiv = document.getElementById('results');
    const checkboxes = resultsDiv.querySelectorAll('.bulk-checkbox input[type="checkbox"]');

    checkboxes.forEach(checkbox => {
        checkbox.checked = false;
    });

    selectedConversations.clear();
    updateBulkToolbar();
}

/**
 * Export selected conversations
 */
async function bulkExport(format) {
    if (selectedConversations.size === 0) {
        alert('Please select at least one conversation to export');
        return;
    }

    if (selectedConversations.size > 100) {
        alert('Maximum 100 conversations can be exported at once');
        return;
    }

    try {
        const params = applySnapshotParam(new URLSearchParams());
        const url = params.toString()
            ? `/api/conversations/bulk-export?${params.toString()}`
            : '/api/conversations/bulk-export';
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                conversation_ids: Array.from(selectedConversations),
                format: format
            })
        });

        if (!response.ok) {
            throw new Error('Export failed');
        }

        // Trigger download
        const blob = await response.blob();
        const blobUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = `searchat_export_${Date.now()}.zip`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(blobUrl);
        a.remove();

        // Show success message
        const countSpan = document.getElementById('bulkCount');
        if (countSpan) {
            const originalText = countSpan.textContent;
            countSpan.textContent = '✓ Export complete!';
            countSpan.style.color = 'hsl(var(--success))';

            setTimeout(() => {
                countSpan.textContent = originalText;
                countSpan.style.color = 'hsl(var(--text-primary))';
            }, 3000);
        }

    } catch (error) {
        console.error('Bulk export failed:', error);
        alert('Failed to export conversations. Please try again.');
    }
}

/**
 * Update toggle button state
 */
function updateToggleButton() {
    const btn = document.getElementById('bulkModeToggle');
    if (btn) {
        if (bulkModeActive) {
            btn.textContent = '✕ Exit Bulk Mode';
            btn.style.borderColor = 'hsl(var(--danger))';
            btn.style.color = 'hsl(var(--danger))';
        } else {
            btn.textContent = 'Bulk Export';
            btn.style.borderColor = 'hsl(var(--accent))';
            btn.style.color = '';
        }
    }
}

/**
 * Check if bulk mode is active
 */
export function isBulkModeActive() {
    return bulkModeActive;
}

/**
 * Add checkbox to a result element
 */
export function addCheckboxToResult(resultElement, conversationId) {
    if (bulkModeActive) {
        const checkbox = createCheckbox(conversationId);
        resultElement.insertBefore(checkbox, resultElement.firstChild);
    }
}
