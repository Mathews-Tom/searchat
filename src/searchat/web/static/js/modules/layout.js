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

let _openDropdown = null;

function closeOpenDropdown() {
    if (_openDropdown) {
        _openDropdown.remove();
        _openDropdown = null;
    }
}

function initFilterChips() {
    const alwaysActive = new Set(['mode', 'sortBy']);

    document.addEventListener('click', (e) => {
        if (_openDropdown && !e.target.closest('.filter-chip') && !e.target.closest('.filter-dropdown')) {
            closeOpenDropdown();
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeOpenDropdown();
    });

    document.querySelectorAll('.filter-chip[data-for]').forEach(chip => {
        const selectId = chip.dataset.for;
        const select = document.getElementById(selectId);
        if (!select) return;

        const valueSpan = chip.querySelector('.filter-value');

        chip.addEventListener('click', (e) => {
            e.stopPropagation();

            // Toggle: if dropdown already open for this chip, close it
            if (_openDropdown && _openDropdown.dataset.forChip === selectId) {
                closeOpenDropdown();
                return;
            }

            closeOpenDropdown();

            const dropdown = document.createElement('div');
            dropdown.className = 'filter-dropdown';
            dropdown.dataset.forChip = selectId;

            Array.from(select.options).forEach((option, idx) => {
                const item = document.createElement('button');
                item.type = 'button';
                item.className = 'filter-dropdown-item';
                item.textContent = option.text;
                if (idx === select.selectedIndex) {
                    item.classList.add('selected');
                }

                item.addEventListener('click', () => {
                    select.selectedIndex = idx;
                    select.dispatchEvent(new Event('change'));
                    closeOpenDropdown();
                });

                dropdown.appendChild(item);
            });

            // Position below the chip
            const rect = chip.getBoundingClientRect();
            dropdown.style.position = 'fixed';
            dropdown.style.top = `${rect.bottom + 4}px`;
            dropdown.style.left = `${rect.left}px`;

            document.body.appendChild(dropdown);
            _openDropdown = dropdown;
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
