// Sidebar section collapse management
const SIDEBAR_STATE_KEY = 'sidebar-sections-state';

function getState() {
    try {
        return JSON.parse(localStorage.getItem(SIDEBAR_STATE_KEY) || '{}');
    } catch {
        return {};
    }
}

function saveState(state) {
    localStorage.setItem(SIDEBAR_STATE_KEY, JSON.stringify(state));
}

export function initSidebarSections() {
    const sidebars = document.querySelectorAll('.sidebar');
    const state = getState();

    sidebars.forEach((sidebar, sidebarIdx) => {
        const sections = sidebar.querySelectorAll('.sidebar-section');
        sections.forEach((section, idx) => {
            const key = `sidebar-${sidebarIdx}-section-${idx}`;
            const heading = section.querySelector('h3');
            if (!heading) return;

            // Create wrapper
            const content = document.createElement('div');
            content.className = 'sidebar-section-content';

            // Move all children after h3 into content wrapper
            while (heading.nextSibling) {
                content.appendChild(heading.nextSibling);
            }
            section.appendChild(content);

            // Make heading clickable
            heading.classList.add('sidebar-section-toggle');
            heading.setAttribute('role', 'button');
            heading.setAttribute('tabindex', '0');

            // Determine default state: Tips and Dataset open, Backup and System Overview closed
            const text = heading.textContent.toLowerCase();
            const defaultOpen = !text.includes('backup') && !text.includes('system overview');
            const isOpen = state[key] !== undefined ? state[key] : defaultOpen;

            if (!isOpen) {
                section.classList.add('section-collapsed');
                heading.setAttribute('aria-expanded', 'false');
            } else {
                heading.setAttribute('aria-expanded', 'true');
            }

            heading.addEventListener('click', () => {
                const collapsed = section.classList.toggle('section-collapsed');
                heading.setAttribute('aria-expanded', (!collapsed).toString());
                const st = getState();
                st[key] = !collapsed;
                saveState(st);
            });

            heading.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    heading.click();
                }
            });
        });
    });
}

export function initSidebarDrawers() {
    if (window.innerWidth > 1400) return;

    const sidebars = document.querySelectorAll('.sidebar');
    if (sidebars.length < 2) return;

    // Create toggle buttons
    const leftToggle = document.createElement('button');
    leftToggle.className = 'sidebar-drawer-toggle sidebar-drawer-toggle-left';
    leftToggle.innerHTML = '☰ Tips';
    leftToggle.setAttribute('aria-label', 'Open search tips');

    const rightToggle = document.createElement('button');
    rightToggle.className = 'sidebar-drawer-toggle sidebar-drawer-toggle-right';
    rightToggle.innerHTML = '🤖 Guide';
    rightToggle.setAttribute('aria-label', 'Open integration guide');

    // Create backdrop
    const backdrop = document.createElement('div');
    backdrop.className = 'sidebar-backdrop';

    document.body.appendChild(leftToggle);
    document.body.appendChild(rightToggle);
    document.body.appendChild(backdrop);

    function closeAll() {
        sidebars.forEach(s => s.classList.remove('drawer-open'));
        backdrop.classList.remove('visible');
    }

    leftToggle.addEventListener('click', () => {
        closeAll();
        sidebars[0].classList.add('drawer-open');
        backdrop.classList.add('visible');
    });

    rightToggle.addEventListener('click', () => {
        closeAll();
        sidebars[1].classList.add('drawer-open');
        backdrop.classList.add('visible');
    });

    backdrop.addEventListener('click', closeAll);

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeAll();
    });

    // Re-check on resize
    let resizeTimer;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => {
            if (window.innerWidth > 1400) {
                closeAll();
                leftToggle.style.display = 'none';
                rightToggle.style.display = 'none';
            } else {
                leftToggle.style.display = '';
                rightToggle.style.display = '';
            }
        }, 200);
    });
}
