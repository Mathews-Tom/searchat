// Keyboard shortcuts handler

let helpModalOpen = false;

/**
 * Initialize keyboard shortcuts
 */
export function initShortcuts() {
    document.addEventListener('keydown', handleKeyPress);
    createHelpModal();
}

/**
 * Handle keyboard shortcuts
 */
function handleKeyPress(e) {
    // Ignore shortcuts when typing in input/textarea elements
    const activeElement = document.activeElement;
    const isInputActive = activeElement.tagName === 'INPUT' ||
                          activeElement.tagName === 'TEXTAREA' ||
                          activeElement.isContentEditable;

    // '?' - Show help modal (works even in inputs)
    if (e.key === '?' && e.shiftKey) {
        e.preventDefault();
        toggleHelpModal();
        return;
    }

    // Escape - Close help modal or clear search
    if (e.key === 'Escape') {
        if (helpModalOpen) {
            e.preventDefault();
            toggleHelpModal();
            return;
        }

        // Clear search if in search box
        if (isInputActive && activeElement.id === 'search') {
            e.preventDefault();
            activeElement.value = '';
            return;
        }
        return;
    }

    // Shortcuts that shouldn't work while typing
    if (isInputActive && activeElement.id !== 'search') {
        return;
    }

    // '/' - Focus search box
    if (e.key === '/') {
        e.preventDefault();
        const searchBox = document.getElementById('search');
        if (searchBox) {
            searchBox.focus();
            searchBox.select();
        }
        return;
    }

    // 'r' - Resume last conversation
    if (e.key === 'r' && !isInputActive) {
        e.preventDefault();
        if (window.resumeSession) {
            window.resumeSession();
        }
        return;
    }

    // 'c' - Focus chat input
    if (e.key === 'c' && !isInputActive) {
        e.preventDefault();
        const chatInput = document.getElementById('chatQuestion');
        if (chatInput) {
            chatInput.focus();
            chatInput.select();
        }
        return;
    }
}

/**
 * Create help modal HTML
 */
function createHelpModal() {
    const modal = document.createElement('div');
    modal.id = 'shortcutsHelpModal';
    modal.style.cssText = `
        display: none;
        position: fixed;
        z-index: 10000;
        left: 0;
        top: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(0, 0, 0, 0.7);
        animation: fadeIn 0.2s ease;
    `;

    modal.innerHTML = `
        <div style="
            position: relative;
            background: hsl(var(--bg-base));
            margin: 10% auto;
            padding: 32px;
            border-radius: 12px;
            max-width: 600px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            animation: slideIn 0.3s ease;
        ">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
                <h2 style="margin: 0; color: hsl(var(--text-primary)); font-family: var(--font-sans);">
                    ⌨️ Keyboard Shortcuts
                </h2>
                <button onclick="window.toggleHelpModal()" style="
                    background: transparent;
                    border: none;
                    font-size: 28px;
                    cursor: pointer;
                    color: hsl(var(--text-tertiary));
                    padding: 0;
                    width: 32px;
                    height: 32px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    border-radius: 4px;
                    transition: all 0.2s;
                " onmouseover="this.style.background='hsl(var(--bg-surface))'" onmouseout="this.style.background='transparent'">
                    ×
                </button>
            </div>

            <div style="display: grid; gap: 16px;">
                <div class="shortcut-item">
                    <kbd style="
                        background: hsl(var(--bg-surface));
                        padding: 4px 8px;
                        border-radius: 4px;
                        font-family: 'JetBrains Mono', monospace;
                        font-size: 13px;
                        border: 1px solid hsl(var(--border-glass));
                        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                    ">?</kbd>
                    <span style="margin-left: 16px; color: hsl(var(--text-primary));">Show this help dialog</span>
                </div>

                <div class="shortcut-item">
                    <kbd style="
                        background: hsl(var(--bg-surface));
                        padding: 4px 8px;
                        border-radius: 4px;
                        font-family: 'JetBrains Mono', monospace;
                        font-size: 13px;
                        border: 1px solid hsl(var(--border-glass));
                        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                    ">/</kbd>
                    <span style="margin-left: 16px; color: hsl(var(--text-primary));">Focus search box</span>
                </div>

                <div class="shortcut-item">
                    <kbd style="
                        background: hsl(var(--bg-surface));
                        padding: 4px 8px;
                        border-radius: 4px;
                        font-family: 'JetBrains Mono', monospace;
                        font-size: 13px;
                        border: 1px solid hsl(var(--border-glass));
                        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                    ">Esc</kbd>
                    <span style="margin-left: 16px; color: hsl(var(--text-primary));">Clear search / Close dialog</span>
                </div>

                <div class="shortcut-item">
                    <kbd style="
                        background: hsl(var(--bg-surface));
                        padding: 4px 8px;
                        border-radius: 4px;
                        font-family: 'JetBrains Mono', monospace;
                        font-size: 13px;
                        border: 1px solid hsl(var(--border-glass));
                        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                    ">r</kbd>
                    <span style="margin-left: 16px; color: hsl(var(--text-primary));">Resume last conversation</span>
                </div>

                <div class="shortcut-item">
                    <kbd style="
                        background: hsl(var(--bg-surface));
                        padding: 4px 8px;
                        border-radius: 4px;
                        font-family: 'JetBrains Mono', monospace;
                        font-size: 13px;
                        border: 1px solid hsl(var(--border-glass));
                        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                    ">c</kbd>
                    <span style="margin-left: 16px; color: hsl(var(--text-primary));">Focus chat input</span>
                </div>

                <div class="shortcut-item">
                    <kbd style="
                        background: hsl(var(--bg-surface));
                        padding: 4px 8px;
                        border-radius: 4px;
                        font-family: 'JetBrains Mono', monospace;
                        font-size: 13px;
                        border: 1px solid hsl(var(--border-glass));
                        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                    ">Enter</kbd>
                    <span style="margin-left: 16px; color: hsl(var(--text-primary));">Search (when in search box)</span>
                </div>
            </div>

            <div style="margin-top: 24px; padding-top: 20px; border-top: 1px solid hsl(var(--border-subtle)); color: hsl(var(--text-tertiary)); font-size: 13px;">
                <p style="margin: 0;">
                    💡 <strong>Tip:</strong> Most shortcuts work from anywhere on the page. Press <kbd style="
                        background: hsl(var(--bg-surface));
                        padding: 2px 6px;
                        border-radius: 3px;
                        font-family: 'JetBrains Mono', monospace;
                        font-size: 12px;
                    ">Esc</kbd> to close this dialog.
                </p>
            </div>
        </div>
    `;

    // Add CSS animations
    const style = document.createElement('style');
    style.textContent = `
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }

        @keyframes slideIn {
            from {
                transform: translateY(-50px);
                opacity: 0;
            }
            to {
                transform: translateY(0);
                opacity: 1;
            }
        }

        .shortcut-item {
            display: flex;
            align-items: center;
            padding: 8px 0;
        }
    `;
    document.head.appendChild(style);

    // Close modal when clicking outside
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            toggleHelpModal();
        }
    });

    document.body.appendChild(modal);
}

/**
 * Toggle help modal visibility
 */
export function toggleHelpModal() {
    const modal = document.getElementById('shortcutsHelpModal');
    if (!modal) return;

    helpModalOpen = !helpModalOpen;
    modal.style.display = helpModalOpen ? 'block' : 'none';

    // Prevent body scroll when modal is open
    document.body.style.overflow = helpModalOpen ? 'hidden' : '';
}
