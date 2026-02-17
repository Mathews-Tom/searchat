// Chat UI handler

import { loadConversationView } from './search.js';

function setStatus(message, isError = false) {
    const status = document.getElementById('chatStatus');
    if (!status) return;
    status.textContent = message;
    status.style.color = isError ? '#f44336' : '';
}

function setSpinner(active) {
    const spinner = document.getElementById('chatSpinner');
    if (!spinner) return;
    spinner.classList.toggle('active', active);
    spinner.setAttribute('aria-hidden', active ? 'false' : 'true');
}

function setAnswer(text) {
    const answer = document.getElementById('chatAnswer');
    if (!answer) return;
    answer.textContent = text;
}

function setSources(sources) {
    const sourcesEl = document.getElementById('chatSources');
    if (!sourcesEl) return;

    if (!sources || sources.length === 0) {
        sourcesEl.style.display = 'none';
        sourcesEl.innerHTML = '';
        return;
    }

    sourcesEl.style.display = 'block';
    const items = sources.map((s) => {
        const range = (s.message_start_index != null && s.message_end_index != null)
            ? `messages ${s.message_start_index}-${s.message_end_index}`
            : 'full conversation';

        const updated = s.updated_at ? new Date(s.updated_at).toLocaleString() : '';
        const tool = s.tool ? String(s.tool).toUpperCase() : '';
        const project = s.project_id ? s.project_id : '';
        const title = s.title ? s.title : s.conversation_id;

        return `
            <div class="chat-source-item">
                <div class="chat-source-main">
                    <div class="chat-source-title">${escapeHtml(title)}</div>
                    <div class="chat-source-meta">
                        ${escapeHtml([tool, project, updated, range].filter(Boolean).join(' · '))}
                    </div>
                </div>
                <button class="chat-source-open" data-conversation-id="${escapeHtml(s.conversation_id)}">Open</button>
            </div>
        `;
    }).join('');

    sourcesEl.innerHTML = `
        <div class="chat-sources-title">Sources</div>
        ${items}
    `;

    for (const btn of sourcesEl.querySelectorAll('button[data-conversation-id]')) {
        btn.addEventListener('click', (event) => {
            const id = event.currentTarget.getAttribute('data-conversation-id');
            if (!id) return;
            loadConversationView(id);
        });
    }
}

let _chatController = null;

function saveChatPreferences() {
    const providerEl = document.getElementById('chatProvider');
    const modelEl = document.getElementById('chatModel');
    const temperatureEl = document.getElementById('chatTemperature');
    const maxTokensEl = document.getElementById('chatMaxTokens');
    const systemPromptEl = document.getElementById('chatSystemPrompt');
    if (providerEl) {
        localStorage.setItem('chatProvider', providerEl.value);
    }
    if (modelEl) {
        localStorage.setItem('chatModel', modelEl.value.trim());
    }

    if (temperatureEl) {
        localStorage.setItem('chatTemperature', temperatureEl.value.trim());
    }
    if (maxTokensEl) {
        localStorage.setItem('chatMaxTokens', maxTokensEl.value.trim());
    }
    if (systemPromptEl) {
        localStorage.setItem('chatSystemPrompt', systemPromptEl.value);
    }
}

function restoreChatPreferences() {
    const providerEl = document.getElementById('chatProvider');
    const modelEl = document.getElementById('chatModel');
    const temperatureEl = document.getElementById('chatTemperature');
    const maxTokensEl = document.getElementById('chatMaxTokens');
    const systemPromptEl = document.getElementById('chatSystemPrompt');
    if (providerEl) {
        const storedProvider = localStorage.getItem('chatProvider');
        if (storedProvider) {
            providerEl.value = storedProvider;
        }
    }
    if (modelEl) {
        const storedModel = localStorage.getItem('chatModel');
        if (storedModel) {
            modelEl.value = storedModel;
        }
    }

    if (temperatureEl) {
        const storedTemp = localStorage.getItem('chatTemperature');
        if (storedTemp) {
            temperatureEl.value = storedTemp;
        }
    }

    if (maxTokensEl) {
        const storedMaxTokens = localStorage.getItem('chatMaxTokens');
        if (storedMaxTokens) {
            maxTokensEl.value = storedMaxTokens;
        }
    }

    if (systemPromptEl) {
        const storedSystemPrompt = localStorage.getItem('chatSystemPrompt');
        if (storedSystemPrompt) {
            systemPromptEl.value = storedSystemPrompt;
        }
    }
}

async function runChatRag() {
    const queryEl = document.getElementById('chatQuery');
    const providerEl = document.getElementById('chatProvider');
    const modelEl = document.getElementById('chatModel');
    const temperatureEl = document.getElementById('chatTemperature');
    const maxTokensEl = document.getElementById('chatMaxTokens');
    const systemPromptEl = document.getElementById('chatSystemPrompt');
    const sendBtn = document.getElementById('chatSend');
    const stopBtn = document.getElementById('chatStop');

    const query = queryEl.value.trim();
    if (!query) {
        setStatus('Enter a question to ask.', true);
        return;
    }

    if (_chatController) {
        _chatController.abort();
    }

    _chatController = new AbortController();
    const abortSignal = _chatController.signal;

    sendBtn.disabled = true;
    if (stopBtn) stopBtn.disabled = false;
    setSpinner(true);
    setStatus('Contacting model...');
    setAnswer('');
    setSources([]);

    const payload = {
        query: query,
        model_provider: providerEl.value,
    };

    const modelName = modelEl.value.trim();
    if (modelName) {
        payload.model_name = modelName;
    }

    if (temperatureEl) {
        const t = _parseOptionalFloat(temperatureEl.value);
        if (t != null) {
            payload.temperature = t;
        }
    }

    if (maxTokensEl) {
        const mt = _parseOptionalInt(maxTokensEl.value);
        if (mt != null) {
            payload.max_tokens = mt;
        }
    }

    if (systemPromptEl) {
        const sp = systemPromptEl.value.trim();
        if (sp) {
            payload.system_prompt = sp;
        }
    }

    saveChatPreferences();

    try {
        const response = await fetch('/api/chat-rag', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            signal: abortSignal,
        });

        if (response.status === 503) {
            const payload = await response.json().catch(() => null);
            if (payload && payload.status === 'warming') {
                // Engine still warming — show spinner and auto-retry.
                setSpinner(true);
                setStatus('Search engine warming up\u2026');
                const delay = (payload.retry_after_ms || 500);
                await new Promise(r => setTimeout(r, delay));
                if (!_chatController?.signal.aborted) {
                    return runChatRag();
                }
                return;
            }
            const msg = payload && payload.detail ? payload.detail : 'Service unavailable.';
            setStatus(msg, true);
            return;
        }

        if (!response.ok) {
            const payload = await response.json().catch(() => null);
            const msg = payload && payload.detail ? payload.detail : 'Chat request failed.';
            setStatus(msg, true);
            return;
        }

        const data = await response.json();
        setStatus('');
        setAnswer(data && data.answer ? data.answer : '');
        setSources(data && data.sources ? data.sources : []);
    } catch (error) {
        if (error.name === 'AbortError') {
            setStatus('Request stopped.');
        } else {
            setStatus(error.message || 'Chat request failed.', true);
        }
    } finally {
        sendBtn.disabled = false;
        if (stopBtn) stopBtn.disabled = true;
        setSpinner(false);
        _chatController = null;
    }
}

function clearChat() {
    const queryEl = document.getElementById('chatQuery');
    if (queryEl) {
        queryEl.value = '';
    }
    setStatus('');
    setAnswer('');
    setSpinner(false);
}

function stopChat() {
    if (_chatController) {
        _chatController.abort();
    }
}

export function initChat() {
    const sendBtn = document.getElementById('chatSend');
    const stopBtn = document.getElementById('chatStop');
    const clearBtn = document.getElementById('chatClear');
    const queryEl = document.getElementById('chatQuery');
    const providerEl = document.getElementById('chatProvider');
    const modelEl = document.getElementById('chatModel');
    const temperatureEl = document.getElementById('chatTemperature');
    const maxTokensEl = document.getElementById('chatMaxTokens');
    const systemPromptEl = document.getElementById('chatSystemPrompt');

    // Add collapse/expand functionality to chat panel
    const chatPanel = document.getElementById('chatPanel');
    const chatHeader = chatPanel?.querySelector('.chat-header');
    if (chatHeader && chatPanel) {
        const toggle = document.createElement('button');
        toggle.className = 'chat-toggle';
        toggle.setAttribute('aria-label', 'Toggle chat panel');
        toggle.setAttribute('aria-expanded', 'true');
        toggle.textContent = '▼';
        chatHeader.style.cursor = 'pointer';
        chatHeader.insertBefore(toggle, chatHeader.firstChild);

        // Collapsed by default; only expand if user previously opened it.
        const savedState = localStorage.getItem('chat-panel-collapsed');
        if (savedState !== 'false') {
            chatPanel.classList.add('collapsed');
            toggle.textContent = '▶';
            toggle.setAttribute('aria-expanded', 'false');
        }

        chatHeader.addEventListener('click', (e) => {
            // Don't toggle when clicking controls inside the header
            if (e.target.closest('.chat-controls') || e.target.closest('select') || e.target.closest('input') || e.target.closest('details')) return;
            const isCollapsed = chatPanel.classList.toggle('collapsed');
            toggle.textContent = isCollapsed ? '▶' : '▼';
            toggle.setAttribute('aria-expanded', (!isCollapsed).toString());
            localStorage.setItem('chat-panel-collapsed', isCollapsed.toString());
        });
    }

    if (sendBtn) sendBtn.addEventListener('click', runChatRag);
    if (stopBtn) {
        stopBtn.addEventListener('click', stopChat);
        stopBtn.disabled = true;
    }
    if (clearBtn) clearBtn.addEventListener('click', clearChat);

    if (queryEl) {
        queryEl.addEventListener('keydown', (event) => {
            if (event.isComposing) {
                return;
            }

            const isEnter = event.key === 'Enter';
            const isSubmit = (event.metaKey || event.ctrlKey) || (!event.shiftKey && !event.altKey);
            if (isEnter && isSubmit) {
                event.preventDefault();
                runChatRag();
            }
        });
    }

    if (providerEl) {
        providerEl.addEventListener('change', saveChatPreferences);
    }

    if (modelEl) {
        modelEl.addEventListener('change', saveChatPreferences);
    }

    if (temperatureEl) {
        temperatureEl.addEventListener('change', saveChatPreferences);
    }

    if (maxTokensEl) {
        maxTokensEl.addEventListener('change', saveChatPreferences);
    }

    if (systemPromptEl) {
        systemPromptEl.addEventListener('change', saveChatPreferences);
    }

    restoreChatPreferences();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function _parseOptionalFloat(value) {
    const trimmed = String(value || '').trim();
    if (!trimmed) return null;
    const parsed = Number.parseFloat(trimmed);
    if (!Number.isFinite(parsed)) return null;
    return parsed;
}

function _parseOptionalInt(value) {
    const trimmed = String(value || '').trim();
    if (!trimmed) return null;
    const parsed = Number.parseInt(trimmed, 10);
    if (!Number.isFinite(parsed)) return null;
    return parsed;
}
