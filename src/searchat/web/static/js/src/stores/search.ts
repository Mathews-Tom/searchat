/** Alpine.js search store — manages search state, filters, pagination, and history. */

import type { SearchMode, SortBy, DateFilter } from "@app-types/api";

interface HistoryEntry {
  query: string;
  mode: SearchMode;
  timestamp: number;
}

export const searchStore = {
  // Search state
  query: "",
  mode: "hybrid" as SearchMode,
  project: "",
  tool: "",
  date: "" as DateFilter,
  dateFrom: "",
  dateTo: "",
  sortBy: "relevance" as SortBy,
  semanticHighlights: false,

  // Pagination
  page: 1,
  pageSize: 20,
  totalPages: 0,
  totalResults: 0,

  // Results state
  loading: false,
  searchTimeMs: 0,

  // Search history
  history: [] as HistoryEntry[],
  maxHistory: 50,

  init() {
    this._restoreState();
    this._loadHistory();
  },

  setQuery(q: string) {
    this.query = q;
  },

  setMode(mode: SearchMode) {
    this.mode = mode;
    this.page = 1;
  },

  setProject(project: string) {
    this.project = project;
    this.page = 1;
  },

  setTool(tool: string) {
    this.tool = tool;
    this.page = 1;
  },

  setDate(date: DateFilter) {
    this.date = date;
    this.page = 1;
  },

  setSortBy(sortBy: SortBy) {
    this.sortBy = sortBy;
    this.page = 1;
  },

  setPage(page: number) {
    this.page = page;
  },

  buildSearchParams(): URLSearchParams {
    const params = new URLSearchParams();
    params.set("q", this.query);
    params.set("mode", this.mode);
    params.set("page", String(this.page));
    params.set("page_size", String(this.pageSize));
    if (this.project) params.set("project", this.project);
    if (this.tool) params.set("tool", this.tool);
    if (this.sortBy !== "relevance") params.set("sort_by", this.sortBy);
    if (this.date === "custom") {
      if (this.dateFrom) params.set("date_from", this.dateFrom);
      if (this.dateTo) params.set("date_to", this.dateTo);
    } else if (this.date) {
      params.set("date", this.date);
    }
    if (this.semanticHighlights) params.set("semantic_highlights", "true");
    return params;
  },

  addToHistory(query: string) {
    if (!query.trim()) return;
    // Remove duplicate if exists
    this.history = this.history.filter((h) => h.query !== query);
    this.history.unshift({
      query,
      mode: this.mode,
      timestamp: Date.now(),
    });
    if (this.history.length > this.maxHistory) {
      this.history = this.history.slice(0, this.maxHistory);
    }
    this._saveHistory();
  },

  clearHistory() {
    this.history = [];
    this._saveHistory();
  },

  saveState() {
    const state = {
      query: this.query,
      mode: this.mode,
      project: this.project,
      tool: this.tool,
      date: this.date,
      dateFrom: this.dateFrom,
      dateTo: this.dateTo,
      sortBy: this.sortBy,
      page: this.page,
      semanticHighlights: this.semanticHighlights,
    };
    sessionStorage.setItem("searchState", JSON.stringify(state));
  },

  _restoreState() {
    const raw = sessionStorage.getItem("searchState");
    if (!raw) return;
    const state = JSON.parse(raw);
    Object.assign(this, state);
  },

  _loadHistory() {
    const raw = localStorage.getItem("searchHistory");
    if (raw) {
      this.history = JSON.parse(raw);
    }
  },

  _saveHistory() {
    localStorage.setItem("searchHistory", JSON.stringify(this.history));
  },
};
