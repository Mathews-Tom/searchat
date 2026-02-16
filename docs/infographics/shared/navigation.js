/**
 * Shared Navigation Component for Infographic Sub-Pages
 * Injects navigation HTML, handles toggle logic, and persists state
 */

(function() {
  'use strict';

  const NAV_STATE_KEY = 'infographic-nav-state';
  const THEME_KEY = 'theme-preference';

  // Navigation HTML template
  const NAV_HTML = `
    <!-- Toggle Button -->
    <button class="nav-toggle" aria-label="Toggle navigation" aria-expanded="false">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="3" y1="6" x2="21" y2="6"/>
        <line x1="3" y1="12" x2="21" y2="12"/>
        <line x1="3" y1="18" x2="21" y2="18"/>
      </svg>
    </button>

    <!-- Navigation Sidebar -->
    <nav class="infographic-nav" aria-label="Infographic navigation">
      <div class="nav-header">
        <h2>Navigation</h2>
        <button class="nav-close" aria-label="Close navigation">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      <a href="/" class="nav-item nav-searchat">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
          <polyline points="9 22 9 12 15 12 15 22"/>
        </svg>
        <span>Back to Searchat</span>
      </a>

      <a href="../infographics.html" class="nav-item nav-home">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="19" y1="12" x2="5" y2="12"/>
          <polyline points="12 19 5 12 12 5"/>
        </svg>
        <span>Back to Infographics</span>
      </a>

      <div class="nav-divider"></div>

      <div class="nav-section">
        <h3>Infographics</h3>
        <a href="rag-chat-pipeline.html" class="nav-item" data-page="rag">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"/>
            <path d="m21 21-4.35-4.35"/>
          </svg>
          <span>RAG Pipeline</span>
        </a>
        <a href="backup-restore-flow.html" class="nav-item" data-page="backup">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 8v13H3V8"/>
            <path d="M1 3h22v5H1z"/>
            <line x1="10" y1="12" x2="14" y2="12"/>
          </svg>
          <span>Backup & Restore</span>
        </a>
        <a href="file-watching-indexing.html" class="nav-item" data-page="filewatching">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
            <circle cx="12" cy="12" r="3"/>
          </svg>
          <span>File Watching</span>
        </a>
        <a href="multi-agent-connectors.html" class="nav-item" data-page="multiagent">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="5" r="3"/>
            <circle cx="5" cy="19" r="3"/>
            <circle cx="19" cy="19" r="3"/>
            <line x1="12" y1="8" x2="12" y2="12"/>
            <line x1="12" y1="12" x2="7" y2="17"/>
            <line x1="12" y1="12" x2="17" y2="17"/>
          </svg>
          <span>Multi-Agent</span>
        </a>
      </div>

      <div class="nav-divider"></div>

      <div class="nav-section">
        <h3>Theme</h3>
        <div class="theme-selector">
          <button class="theme-option" data-theme="light" aria-label="Light theme">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="5"/>
              <line x1="12" y1="1" x2="12" y2="3"/>
              <line x1="12" y1="21" x2="12" y2="23"/>
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
              <line x1="1" y1="12" x2="3" y2="12"/>
              <line x1="21" y1="12" x2="23" y2="12"/>
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
            </svg>
            <span>Light</span>
          </button>
          <button class="theme-option" data-theme="dark" aria-label="Dark theme">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
            </svg>
            <span>Dark</span>
          </button>
          <button class="theme-option" data-theme="system" aria-label="System theme">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="2" y="3" width="20" height="14" rx="2"/>
              <line x1="8" y1="21" x2="16" y2="21"/>
              <line x1="12" y1="17" x2="12" y2="21"/>
            </svg>
            <span>System</span>
          </button>
        </div>
      </div>
    </nav>

    <!-- Overlay -->
    <div class="nav-overlay" aria-hidden="true"></div>
  `;

  /**
   * Initialize navigation on page load
   */
  function initNavigation() {
    const currentPage = document.body.dataset.page;

    // Inject navigation HTML
    document.body.insertAdjacentHTML('afterbegin', NAV_HTML);

    // Inject breadcrumb
    const pageNames = {
      'rag': 'RAG Pipeline',
      'backup': 'Backup & Restore',
      'filewatching': 'File Watching',
      'multiagent': 'Multi-Agent Connectors'
    };
    const pageName = pageNames[currentPage] || document.title.replace('Searchat — ', '');
    const breadcrumbHTML = `
      <nav class="breadcrumb" aria-label="Breadcrumb">
        <a href="/">Searchat</a>
        <span class="breadcrumb-sep">›</span>
        <a href="../infographics.html">Infographics</a>
        <span class="breadcrumb-sep">›</span>
        <span class="breadcrumb-current">${pageName}</span>
      </nav>
    `;
    document.body.insertAdjacentHTML('afterbegin', breadcrumbHTML);

    // Highlight current page
    highlightCurrentPage(currentPage);

    // Load saved state
    loadNavState();

    // Load theme state
    loadThemeState();

    // Attach event listeners
    attachEventListeners();
  }

  /**
   * Highlight the current page in navigation
   */
  function highlightCurrentPage(page) {
    if (!page) return;

    const navItems = document.querySelectorAll('.nav-item[data-page]');
    navItems.forEach(item => {
      if (item.dataset.page === page) {
        item.classList.add('active');
      }
    });
  }

  /**
   * Load navigation state from localStorage
   */
  function loadNavState() {
    const savedState = localStorage.getItem(NAV_STATE_KEY);
    if (savedState === 'open') {
      document.body.classList.add('nav-open');
      updateToggleAriaExpanded(true);
    }
  }

  /**
   * Save navigation state to localStorage
   */
  function saveNavState(isOpen) {
    localStorage.setItem(NAV_STATE_KEY, isOpen ? 'open' : 'closed');
  }

  /**
   * Toggle navigation visibility
   */
  function toggleNav() {
    const isOpen = document.body.classList.toggle('nav-open');
    updateToggleAriaExpanded(isOpen);
    saveNavState(isOpen);
  }

  /**
   * Close navigation
   */
  function closeNav() {
    document.body.classList.remove('nav-open');
    updateToggleAriaExpanded(false);
    saveNavState(false);
  }

  /**
   * Update aria-expanded attribute on toggle button
   */
  function updateToggleAriaExpanded(isOpen) {
    const toggleBtn = document.querySelector('.nav-toggle');
    if (toggleBtn) {
      toggleBtn.setAttribute('aria-expanded', isOpen.toString());
    }
  }

  /**
   * Load theme state and apply
   */
  function loadThemeState() {
    const savedTheme = localStorage.getItem(THEME_KEY) || 'system';
    applyTheme(savedTheme);
    updateThemeButtons(savedTheme);
  }

  /**
   * Apply theme to document
   */
  function applyTheme(theme) {
    if (theme === 'system') {
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      document.documentElement.dataset.theme = prefersDark ? 'dark' : 'light';
    } else {
      document.documentElement.dataset.theme = theme;
    }
  }

  /**
   * Update theme button active state
   */
  function updateThemeButtons(theme) {
    const themeButtons = document.querySelectorAll('.theme-option');
    themeButtons.forEach(btn => {
      btn.classList.toggle('active', btn.dataset.theme === theme);
    });
  }

  /**
   * Handle theme change
   */
  function changeTheme(theme) {
    localStorage.setItem(THEME_KEY, theme);
    applyTheme(theme);
    updateThemeButtons(theme);
  }

  /**
   * Attach all event listeners
   */
  function attachEventListeners() {
    // Toggle button
    const toggleBtn = document.querySelector('.nav-toggle');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', toggleNav);
    }

    // Close button
    const closeBtn = document.querySelector('.nav-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', closeNav);
    }

    // Overlay
    const overlay = document.querySelector('.nav-overlay');
    if (overlay) {
      overlay.addEventListener('click', closeNav);
    }

    // Theme buttons
    const themeButtons = document.querySelectorAll('.theme-option');
    themeButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        changeTheme(btn.dataset.theme);
      });
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', handleKeyPress);

    // Listen for storage events (cross-tab sync)
    window.addEventListener('storage', handleStorageChange);

    // Listen for system theme changes
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    mediaQuery.addEventListener('change', () => {
      const currentTheme = localStorage.getItem(THEME_KEY) || 'system';
      if (currentTheme === 'system') {
        applyTheme('system');
      }
    });
  }

  /**
   * Handle keyboard shortcuts
   */
  function handleKeyPress(e) {
    // Escape key to close navigation
    if (e.key === 'Escape' && document.body.classList.contains('nav-open')) {
      closeNav();
    }
  }

  /**
   * Handle storage changes (cross-tab sync)
   */
  function handleStorageChange(e) {
    if (e.key === NAV_STATE_KEY) {
      const isOpen = e.newValue === 'open';
      document.body.classList.toggle('nav-open', isOpen);
      updateToggleAriaExpanded(isOpen);
    } else if (e.key === THEME_KEY) {
      const newTheme = e.newValue || 'system';
      applyTheme(newTheme);
      updateThemeButtons(newTheme);
    }
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNavigation);
  } else {
    initNavigation();
  }
})();
