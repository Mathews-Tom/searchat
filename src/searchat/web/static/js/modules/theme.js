// Theme Management — 3-way: light / dark / auto

const themes = {
    light: {
        "--bg-base": "240 20% 97%",
        "--bg-elevated": "0 0% 100%",
        "--bg-glass": "0 0% 100% / 0.55",
        "--bg-glass-hover": "0 0% 100% / 0.72",
        "--bg-glass-active": "0 0% 100% / 0.85",
        "--bg-surface": "220 14% 96%",
        "--bg-surface-hover": "220 14% 93%",
        "--bg-overlay": "220 20% 96% / 0.8",
        "--border-glass": "0 0% 100% / 0.6",
        "--border-subtle": "220 13% 91%",
        "--border-focus": "221 83% 53%",
        "--text-primary": "220 14% 10%",
        "--text-secondary": "220 9% 43%",
        "--text-tertiary": "220 9% 60%",
        "--text-inverse": "0 0% 100%",
        "--accent": "221 83% 53%",
        "--accent-hover": "221 83% 47%",
        "--accent-subtle": "221 83% 53% / 0.08",
        "--accent-glow": "221 83% 53% / 0.15",
        "--success": "142 71% 45%",
        "--warning": "38 92% 50%",
        "--danger": "0 72% 51%",
        "--danger-subtle": "0 72% 51% / 0.08",
        "--shadow-sm": "0 1px 2px hsl(220 14% 10% / 0.04), 0 1px 3px hsl(220 14% 10% / 0.03)",
        "--shadow-md": "0 4px 6px hsl(220 14% 10% / 0.04), 0 2px 4px hsl(220 14% 10% / 0.03)",
        "--shadow-lg": "0 10px 25px hsl(220 14% 10% / 0.06), 0 4px 10px hsl(220 14% 10% / 0.04)",
        "--shadow-glass": "0 8px 32px hsl(220 14% 10% / 0.06), inset 0 1px 0 hsl(0 0% 100% / 0.6)",
        "--blur-glass": "20px",
        "--blur-bg": "40px",
        "--gradient-mesh": "radial-gradient(ellipse at 20% 50%, hsl(221 83% 53% / 0.04) 0%, transparent 50%), radial-gradient(ellipse at 80% 20%, hsl(262 83% 58% / 0.04) 0%, transparent 50%), radial-gradient(ellipse at 50% 80%, hsl(190 80% 50% / 0.03) 0%, transparent 50%)",
        "--noise-opacity": "0.015",
        "--tag-bg": "221 83% 53% / 0.08",
        "--tag-text": "221 83% 40%",
        "--scrollbar-track": "220 14% 96%",
        "--scrollbar-thumb": "220 9% 82%",
        "--code-bg": "220 14% 96%"
    },
    dark: {
        "--bg-base": "224 25% 8%",
        "--bg-elevated": "224 22% 12%",
        "--bg-glass": "224 22% 14% / 0.6",
        "--bg-glass-hover": "224 22% 16% / 0.72",
        "--bg-glass-active": "224 22% 18% / 0.85",
        "--bg-surface": "224 20% 14%",
        "--bg-surface-hover": "224 20% 18%",
        "--bg-overlay": "224 25% 8% / 0.85",
        "--border-glass": "224 15% 22% / 0.6",
        "--border-subtle": "224 15% 20%",
        "--border-focus": "217 91% 60%",
        "--text-primary": "220 14% 95%",
        "--text-secondary": "220 9% 65%",
        "--text-tertiary": "220 9% 46%",
        "--text-inverse": "220 14% 10%",
        "--accent": "217 91% 60%",
        "--accent-hover": "217 91% 67%",
        "--accent-subtle": "217 91% 60% / 0.1",
        "--accent-glow": "217 91% 60% / 0.12",
        "--success": "142 71% 45%",
        "--warning": "38 92% 50%",
        "--danger": "0 72% 55%",
        "--danger-subtle": "0 72% 55% / 0.1",
        "--shadow-sm": "0 1px 2px hsl(0 0% 0% / 0.2), 0 1px 3px hsl(0 0% 0% / 0.15)",
        "--shadow-md": "0 4px 6px hsl(0 0% 0% / 0.2), 0 2px 4px hsl(0 0% 0% / 0.15)",
        "--shadow-lg": "0 10px 25px hsl(0 0% 0% / 0.3), 0 4px 10px hsl(0 0% 0% / 0.2)",
        "--shadow-glass": "0 8px 32px hsl(0 0% 0% / 0.25), inset 0 1px 0 hsl(0 0% 100% / 0.04)",
        "--blur-glass": "20px",
        "--blur-bg": "40px",
        "--gradient-mesh": "radial-gradient(ellipse at 20% 50%, hsl(217 91% 60% / 0.06) 0%, transparent 50%), radial-gradient(ellipse at 80% 20%, hsl(262 83% 58% / 0.05) 0%, transparent 50%), radial-gradient(ellipse at 50% 80%, hsl(190 80% 50% / 0.04) 0%, transparent 50%)",
        "--noise-opacity": "0.03",
        "--tag-bg": "217 91% 60% / 0.12",
        "--tag-text": "217 91% 72%",
        "--scrollbar-track": "224 20% 12%",
        "--scrollbar-thumb": "224 15% 26%",
        "--code-bg": "224 20% 10%"
    }
};

function resolveTheme(mode) {
    if (mode === 'auto') {
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    return mode;
}

function migratePreference(saved) {
    if (saved === 'future' || saved === 'system') return 'dark';
    if (saved === 'bare') return 'light';
    if (['light', 'dark', 'auto'].includes(saved)) return saved;
    return 'auto';
}

export function applyTheme(resolved) {
    document.documentElement.setAttribute('data-theme', resolved);
    const tokens = themes[resolved];
    if (tokens) {
        for (const [k, v] of Object.entries(tokens)) {
            document.documentElement.style.setProperty(k, v);
        }
    }
}

function updateSwitcherUI(mode) {
    const btns = document.querySelectorAll('.theme-switcher-btn');
    btns.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.themeMode === mode);
    });
}

export function setTheme(mode) {
    localStorage.setItem('theme-preference', mode);
    applyTheme(resolveTheme(mode));
    updateSwitcherUI(mode);
}

export function initTheme() {
    const saved = migratePreference(localStorage.getItem('theme-preference') || 'auto');
    localStorage.setItem('theme-preference', saved);

    applyTheme(resolveTheme(saved));
    updateSwitcherUI(saved);

    // Bind 3-way switcher buttons
    const switcher = document.getElementById('themeSwitcher');
    if (switcher) {
        switcher.addEventListener('click', (e) => {
            const btn = e.target.closest('.theme-switcher-btn');
            if (!btn) return;
            const mode = btn.dataset.themeMode;
            if (mode) setTheme(mode);
        });
    }

    // Listen for OS preference changes to update auto mode in real-time
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
        const current = localStorage.getItem('theme-preference') || 'auto';
        if (current === 'auto') {
            applyTheme(resolveTheme('auto'));
        }
    });
}
