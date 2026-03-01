/** Alpine.js layout store — manages sidebar, navigation, and modal state. */

export const layoutStore = {
  sidebarCollapsed: false,
  rightPanelOpen: false,
  activeNav: "search" as string,
  helpModalOpen: false,
  bulkMode: false,

  init() {
    const saved = localStorage.getItem("sidebarCollapsed");
    if (saved !== null) {
      this.sidebarCollapsed = saved === "true";
    }
  },

  toggleSidebar() {
    this.sidebarCollapsed = !this.sidebarCollapsed;
    localStorage.setItem("sidebarCollapsed", String(this.sidebarCollapsed));
  },

  toggleRightPanel() {
    this.rightPanelOpen = !this.rightPanelOpen;
  },

  setActiveNav(nav: string) {
    this.activeNav = nav;
  },

  toggleHelpModal() {
    this.helpModalOpen = !this.helpModalOpen;
  },

  toggleBulkMode() {
    this.bulkMode = !this.bulkMode;
  },
};
