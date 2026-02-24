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

