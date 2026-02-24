// layout.js — Sidebar toggle, Cmd+K focus, filter chip proxies, nav highlight

export function initLayout() {
    initSidebarToggles();
    initSearchShortcut();
    initFilterChips();
    initNavHighlight();
}

function initSidebarToggles() {
    const container = document.querySelector('.container');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const rightToggle = document.getElementById('rightPanelToggle');

    if (!container) return;

    if (localStorage.getItem('sidebar-collapsed') === 'true') {
        container.classList.add('sidebar-collapsed');
    }
    if (localStorage.getItem('right-collapsed') === 'true') {
        container.classList.add('right-collapsed');
    }

    sidebarToggle?.addEventListener('click', () => {
        container.classList.toggle('sidebar-collapsed');
        localStorage.setItem('sidebar-collapsed', container.classList.contains('sidebar-collapsed'));
    });

    rightToggle?.addEventListener('click', () => {
        container.classList.toggle('right-collapsed');
        localStorage.setItem('right-collapsed', container.classList.contains('right-collapsed'));
    });
}

function initSearchShortcut() {
    document.addEventListener('keydown', (e) => {
        if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
            e.preventDefault();
            document.getElementById('search')?.focus();
        }
    });
}

function initFilterChips() {
    // Selects where index 0 is "all/any" (not active), vs selects where
    // every value is a real filter (always active).
    const alwaysActive = new Set(['mode', 'sortBy']);

    document.querySelectorAll('.filter-chip[data-for]').forEach(chip => {
        const selectId = chip.dataset.for;
        const select = document.getElementById(selectId);
        if (!select) return;

        const valueSpan = chip.querySelector('.filter-value');

        chip.addEventListener('click', () => {
            select.focus();
            select.dispatchEvent(new MouseEvent('mousedown'));
        });

        function sync() {
            const text = select.options[select.selectedIndex]?.text || '';
            if (valueSpan) valueSpan.textContent = text;
            const isActive = alwaysActive.has(selectId) || select.selectedIndex > 0;
            chip.classList.toggle('active', isActive);
        }

        select.addEventListener('change', sync);
        sync();
    });
}

function initNavHighlight() {
    document.querySelectorAll('.nav-item[data-action]').forEach(item => {
        item.addEventListener('click', () => {
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            item.classList.add('active');
        });
    });
}
