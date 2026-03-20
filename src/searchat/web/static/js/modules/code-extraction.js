// Code extraction functionality

function copyIconSvg() {
    return `
        <svg class="copy-action-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <rect x="9" y="9" width="10" height="10" rx="2" stroke="currentColor" stroke-width="2"></rect>
            <path d="M15 9V7a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2" stroke="currentColor" stroke-width="2"></path>
        </svg>
    `;
}

function checkIconSvg() {
    return `
        <svg class="copy-action-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M20 6 9 17l-5-5" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"></path>
        </svg>
    `;
}

/**
 * Load and display code blocks for a conversation
 */
export async function loadCodeBlocks(conversationId, container) {
    container.innerHTML = '<div class="loading">Loading code blocks...</div>';

    try {
        const response = await fetch(`/api/conversation/${conversationId}/code`);
        if (!response.ok) {
            const payload = await response.json().catch(() => null);
            const msg = payload && payload.detail ? payload.detail : 'Failed to load code blocks';
            container.innerHTML = `<div style="color: hsl(var(--danger));">${msg}</div>`;
            return;
        }

        const data = await response.json();

        if (!data.code_blocks || data.code_blocks.length === 0) {
            container.innerHTML = `
                <div style="
                    text-align: center;
                    padding: 40px 20px;
                    color: hsl(var(--text-tertiary));
                ">
                    <div style="font-size: 48px; margin-bottom: 16px;">📄</div>
                    <div style="font-size: 16px; margin-bottom: 8px;">No code blocks found</div>
                    <div style="font-size: 13px;">This conversation doesn't contain any code snippets</div>
                </div>
            `;
            return;
        }

        // Group code blocks by language
        const byLanguage = {};
        data.code_blocks.forEach(block => {
            if (!byLanguage[block.language]) {
                byLanguage[block.language] = [];
            }
            byLanguage[block.language].push(block);
        });

        // Build summary header
        const languages = Object.keys(byLanguage).sort();
        const summary = languages.map(lang =>
            `${lang} (${byLanguage[lang].length})`
        ).join(', ');

        let html = `
            <div style="
                background: hsl(var(--bg-surface));
                padding: 16px;
                border-radius: 8px;
                margin-bottom: 20px;
                border: 1px solid hsl(var(--border-glass));
            ">
                <div style="font-size: 16px; font-weight: 500; color: hsl(var(--text-primary)); margin-bottom: 8px;">
                    📊 ${data.total_blocks} Code Block${data.total_blocks !== 1 ? 's' : ''} Found
                </div>
                <div style="font-size: 13px; color: hsl(var(--text-tertiary));">
                    ${summary}
                </div>
            </div>
        `;

        // Add filter buttons
        html += `
            <div style="margin-bottom: 20px; display: flex; flex-wrap: wrap; gap: 8px;">
                <button class="lang-filter active" data-lang="all" style="
                    padding: 6px 12px;
                    background: hsl(var(--accent));
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-size: 13px;
                    cursor: pointer;
                    font-family: var(--font-sans);
                ">
                    All (${data.total_blocks})
                </button>
        `;

        languages.forEach(lang => {
            html += `
                <button class="lang-filter" data-lang="${lang}" style="
                    padding: 6px 12px;
                    background: hsl(var(--bg-surface));
                    color: hsl(var(--text-primary));
                    border: 1px solid hsl(var(--border-glass));
                    border-radius: 6px;
                    font-size: 13px;
                    cursor: pointer;
                    font-family: var(--font-sans);
                ">
                    ${lang} (${byLanguage[lang].length})
                </button>
            `;
        });

        html += '</div>';

        // Add code blocks container
        html += '<div id="codeBlocksContainer">';

        data.code_blocks.forEach((block, index) => {
            const roleClass = block.role === 'user' ? 'user' : 'assistant';
            const roleLabel = block.role === 'user' ? 'USER' : 'ASSISTANT';
            const languageSource = block.language_source || 'detected';

            html += `
                <div class="code-block-item" data-language="${block.language}" data-language-source="${languageSource}" style="
                    background: hsl(var(--bg-elevated));
                    border: 1px solid hsl(var(--border-glass));
                    border-radius: 8px;
                    margin-bottom: 16px;
                    overflow: hidden;
                ">
                    <div style="
                        background: hsl(var(--bg-surface));
                        padding: 10px 16px;
                        border-bottom: 1px solid hsl(var(--border-glass));
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                    ">
                        <div style="display: flex; align-items: center; gap: 12px;">
                            <span class="role-badge ${roleClass}" style="
                                padding: 4px 8px;
                                border-radius: 4px;
                                font-size: 11px;
                                font-weight: 500;
                            ">
                                ${roleLabel}
                            </span>
                            <span style="
                                font-family: var(--font-mono);
                                font-size: 12px;
                                color: hsl(var(--text-primary));
                                background: hsl(var(--bg-elevated));
                                padding: 4px 8px;
                                border-radius: 4px;
                            ">
                                ${block.language}
                            </span>
                            <span style="font-size: 12px; color: hsl(var(--text-tertiary));">
                                ${block.lines} line${block.lines !== 1 ? 's' : ''}
                            </span>
                        </div>
                        <button class="code-copy-trigger" type="button" data-copy-index="${index}" title="Copy code" aria-label="Copy code" style="
                            padding: 4px 8px;
                            background: transparent;
                            border: 1px solid hsl(var(--border-glass));
                            border-radius: 4px;
                            color: hsl(var(--text-primary));
                            cursor: pointer;
                            transition: all 0.2s;
                            display: inline-flex;
                            align-items: center;
                            justify-content: center;
                        ">
                            ${copyIconSvg()}
                        </button>
                    </div>
                    <pre id="code-${index}" style="
                        margin: 0;
                        padding: 16px;
                        background: hsl(var(--code-bg));
                        overflow-x: auto;
                    "><code class="pygments" style="
                        font-family: var(--font-mono);
                        font-size: 13px;
                        line-height: 1.5;
                        color: hsl(var(--text-primary));
                    ">${escapeHtml(block.code)}</code></pre>
                </div>
            `;
        });

        html += '</div>';

        container.innerHTML = html;

        // Apply hybrid syntax highlighting:
        // 1) highlight blocks with explicit fence language
        // 2) then attempt guessing for the remaining blocks
        await highlightBlocks(container, data.code_blocks, { mode: 'fence' });
        scheduleIdle(async () => {
            await highlightBlocks(container, data.code_blocks, { mode: 'guess' });
        });

        // Add event listeners to filter buttons
        container.querySelectorAll('.lang-filter').forEach(btn => {
            btn.addEventListener('click', () => {
                const lang = btn.dataset.lang;

                // Update active button
                container.querySelectorAll('.lang-filter').forEach(b => {
                    b.classList.remove('active');
                    b.style.background = 'hsl(var(--bg-surface))';
                    b.style.color = 'hsl(var(--text-primary))';
                });
                btn.classList.add('active');
                btn.style.background = 'hsl(var(--accent))';
                btn.style.color = 'white';

                // Filter code blocks
                container.querySelectorAll('.code-block-item').forEach(item => {
                    if (lang === 'all' || item.dataset.language === lang) {
                        item.style.display = 'block';
                    } else {
                        item.style.display = 'none';
                    }
                });
            });
        });

        container.querySelectorAll('.code-copy-trigger').forEach(btn => {
            btn.addEventListener('click', () => {
                const index = Number(btn.dataset.copyIndex);
                copyCode(index, btn);
            });
        });

        // Store code blocks for copying
        window._codeBlocks = data.code_blocks;

    } catch (error) {
        container.innerHTML = `<div style="color: hsl(var(--danger));">Error: ${error.message}</div>`;
    }
}

async function highlightBlocks(container, blocks, { mode }) {
    const items = Array.from(container.querySelectorAll('.code-block-item'));
    const targets = [];

    for (let i = 0; i < blocks.length; i++) {
        const block = blocks[i];
        const item = items[i];
        if (!block || !item) continue;

        const source = item.dataset.languageSource || block.language_source || 'detected';
        const normalizedLanguage = String(block.language || '').toLowerCase();
        const isFence = source === 'fence';
        if (mode === 'fence' && !isFence) continue;
        if (mode === 'guess' && isFence) continue;
        if (mode === 'guess' && ['plaintext', 'text', 'plain'].includes(normalizedLanguage)) continue;

        targets.push({
            index: i,
            code: block.code,
            language: isFence ? block.language : null,
            language_source: isFence ? 'fence' : 'detected',
        });
    }

    if (targets.length === 0) return;

    try {
        const response = await fetch('/api/code/highlight', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ blocks: targets.map(t => ({
                code: t.code,
                language: t.language,
                language_source: t.language_source,
            })) }),
        });
        if (!response.ok) {
            return;
        }
        const payload = await response.json();
        const results = Array.isArray(payload.results) ? payload.results : [];

        for (let j = 0; j < targets.length; j++) {
            const t = targets[j];
            const r = results[j];
            if (!r || typeof r.html !== 'string') continue;
            const pre = container.querySelector(`#code-${t.index}`);
            const codeEl = pre ? pre.querySelector('code') : null;
            if (!codeEl) continue;
            codeEl.classList.add('pygments');
            codeEl.innerHTML = r.html;
        }
    } catch (error) {
        // Ignore highlighting failures; code is already visible as plain text.
        return;
    }
}

function scheduleIdle(callback) {
    if (typeof window.requestIdleCallback === 'function') {
        window.requestIdleCallback(() => {
            callback();
        }, { timeout: 1500 });
        return;
    }
    setTimeout(() => { callback(); }, 0);
}

/**
 * Copy code block to clipboard
 */
export function copyCode(index, buttonEl = null) {
    if (!window._codeBlocks || !window._codeBlocks[index]) return;

    const code = window._codeBlocks[index].code;
    const button = buttonEl || document.querySelector(`.code-copy-trigger[data-copy-index="${index}"]`);
    if (!(button instanceof HTMLElement)) return;

    navigator.clipboard.writeText(code).then(() => {
        button.innerHTML = checkIconSvg();
        button.style.background = 'hsl(var(--success))';
        button.style.color = 'white';
        button.style.borderColor = 'hsl(var(--success))';
        button.setAttribute('title', 'Copied');
        button.setAttribute('aria-label', 'Copied');

        setTimeout(() => {
            button.innerHTML = copyIconSvg();
            button.style.background = 'transparent';
            button.style.color = 'hsl(var(--text-primary))';
            button.style.borderColor = 'hsl(var(--border-glass))';
            button.setAttribute('title', 'Copy code');
            button.setAttribute('aria-label', 'Copy code');
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy code:', err);
        button.style.borderColor = 'hsl(var(--danger))';
        button.style.color = 'hsl(var(--danger))';
        button.setAttribute('title', 'Copy failed');
        button.setAttribute('aria-label', 'Copy failed');
        setTimeout(() => {
            button.style.borderColor = 'hsl(var(--border-glass))';
            button.style.color = 'hsl(var(--text-primary))';
            button.setAttribute('title', 'Copy code');
            button.setAttribute('aria-label', 'Copy code');
        }, 2000);
    });
}

/**
 * Escape HTML entities
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
