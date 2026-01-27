// Chat UI handler

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

function appendAnswer(text) {
    const answer = document.getElementById('chatAnswer');
    if (!answer) return;
    answer.textContent += text;
}

let _chatController = null;

function saveChatPreferences() {
    const providerEl = document.getElementById('chatProvider');
    const modelEl = document.getElementById('chatModel');
    if (providerEl) {
        localStorage.setItem('chatProvider', providerEl.value);
    }
    if (modelEl) {
        localStorage.setItem('chatModel', modelEl.value.trim());
    }
}

function restoreChatPreferences() {
    const providerEl = document.getElementById('chatProvider');
    const modelEl = document.getElementById('chatModel');
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
}

async function streamChat() {
    const queryEl = document.getElementById('chatQuery');
    const providerEl = document.getElementById('chatProvider');
    const modelEl = document.getElementById('chatModel');
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

    const payload = {
        query: query,
        model_provider: providerEl.value,
    };

    const modelName = modelEl.value.trim();
    if (modelName) {
        payload.model_name = modelName;
    }

    saveChatPreferences();

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            signal: abortSignal,
        });

        if (response.status === 503) {
            const payload = await response.json().catch(() => null);
            const msg = payload && payload.detail ? payload.detail : 'Search engine warming, please retry.';
            setStatus(msg, true);
            return;
        }

        if (!response.ok) {
            const payload = await response.json().catch(() => null);
            const msg = payload && payload.detail ? payload.detail : 'Chat request failed.';
            setStatus(msg, true);
            return;
        }

        if (!response.body) {
            setStatus('Streaming is not supported by the browser.', true);
            return;
        }

        setStatus('');
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let done = false;

        while (!done) {
            const result = await reader.read();
            done = result.done;
            if (result.value) {
                appendAnswer(decoder.decode(result.value, { stream: !done }));
            }
        }
    } catch (error) {
        if (error.name === 'AbortError') {
            setStatus('Streaming stopped.');
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

    if (sendBtn) sendBtn.addEventListener('click', streamChat);
    if (stopBtn) {
        stopBtn.addEventListener('click', stopChat);
        stopBtn.disabled = true;
    }
    if (clearBtn) clearBtn.addEventListener('click', clearChat);

    if (queryEl) {
        queryEl.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
                event.preventDefault();
                streamChat();
            }
        });
    }

    if (providerEl) {
        providerEl.addEventListener('change', saveChatPreferences);
    }

    if (modelEl) {
        modelEl.addEventListener('change', saveChatPreferences);
    }

    restoreChatPreferences();
}
