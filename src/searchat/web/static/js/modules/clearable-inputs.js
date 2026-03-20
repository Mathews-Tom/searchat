function clearIconSvg() {
    return `
        <svg class="clearable-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M18 6 6 18M6 6l12 12" stroke="currentColor" stroke-width="2.25" stroke-linecap="round"></path>
        </svg>
    `;
}

const CLEARABLE_SELECTOR = 'input[type="text"], input[type="search"], textarea';

function isEligibleField(field) {
    if (!(field instanceof HTMLElement)) return false;
    if (field.dataset.clearableOptOut === 'true') return false;
    if (field.disabled || field.readOnly) return false;
    if (!field.parentElement) return false;
    return true;
}

function updateButtonVisibility(field, button) {
    const hasValue = Boolean(field.value && field.value.length > 0);
    button.hidden = !hasValue;
    button.setAttribute('aria-hidden', hasValue ? 'false' : 'true');
}

function decorateField(field) {
    if (!isEligibleField(field) || field.dataset.clearableBound === 'true') return;

    const host = field.parentElement;
    if (!host) return;

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'clearable-button';
    button.innerHTML = clearIconSvg();
    button.setAttribute('aria-label', 'Clear text');
    button.setAttribute('title', 'Clear');
    button.hidden = true;

    if (field.tagName === 'TEXTAREA') {
        button.classList.add('is-textarea');
    }

    host.classList.add('clearable-host');
    field.classList.add('clearable-input');
    host.appendChild(button);

    const sync = () => updateButtonVisibility(field, button);

    field.addEventListener('input', sync);
    field.addEventListener('change', sync);
    field.addEventListener('blur', sync);

    button.addEventListener('click', () => {
        field.value = '';
        field.dispatchEvent(new Event('input', { bubbles: true }));
        field.dispatchEvent(new Event('change', { bubbles: true }));
        sync();
        field.focus();
    });

    field.dataset.clearableBound = 'true';
    sync();
}

function decorateTree(root) {
    if (!(root instanceof HTMLElement || root instanceof Document)) return;

    if (root instanceof HTMLElement && root.matches(CLEARABLE_SELECTOR)) {
        decorateField(root);
    }

    root.querySelectorAll?.(CLEARABLE_SELECTOR).forEach((field) => {
        decorateField(field);
    });
}

export function initClearableInputs() {
    decorateTree(document);

    const observer = new MutationObserver((mutations) => {
        for (const mutation of mutations) {
            mutation.addedNodes.forEach((node) => {
                if (node instanceof HTMLElement) {
                    decorateTree(node);
                }
            });
        }
    });

    observer.observe(document.body, { childList: true, subtree: true });
}
