/** API response type definitions for Searchat frontend. */

export interface SearchResult {
  conversation_id: string;
  title: string;
  project_id: string;
  file_path: string;
  message_count: number;
  score: number;
  snippet: string;
  created_at: string;
  updated_at: string;
  tool: string;
  bookmarked?: boolean;
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  query: string;
  mode: string;
  page: number;
  page_size: number;
  total_pages: number;
  search_time_ms: number;
}

export interface Conversation {
  conversation_id: string;
  title: string;
  project_id: string;
  file_path: string;
  message_count: number;
  messages: Message[];
  created_at: string;
  updated_at: string;
}

export interface Message {
  role: "user" | "assistant" | "system";
  content: string;
  timestamp?: string;
}

export interface Bookmark {
  conversation_id: string;
  title: string;
  project_id: string;
  bookmarked_at: string;
  note?: string;
}

export interface BackupInfo {
  name: string;
  created_at: string;
  size_bytes: number;
  has_parquet: boolean;
  has_faiss: boolean;
  has_config: boolean;
  description?: string;
}

export interface SavedQuery {
  id: string;
  name: string;
  description?: string;
  query: string;
  mode: string;
  project?: string;
  tool?: string;
  date?: string;
  sort_by?: string;
  created_at: string;
}

export interface ProjectSummary {
  project_id: string;
  conversation_count: number;
  message_count: number;
  tools: string[];
}

export interface AnalyticsSummary {
  total_conversations: number;
  total_messages: number;
  total_projects: number;
  tools_breakdown: Record<string, number>;
}

export interface ChatRequest {
  query: string;
  provider?: string;
  model?: string;
  temperature?: number;
  max_tokens?: number;
  system_prompt?: string;
}

export interface ChatResponse {
  answer: string;
  sources: ChatSource[];
  model: string;
  provider: string;
}

export interface ChatSource {
  conversation_id: string;
  title: string;
  score: number;
  snippet: string;
}

export interface DashboardConfig {
  id: string;
  name: string;
  description?: string;
  widgets: DashboardWidget[];
  created_at: string;
}

export interface DashboardWidget {
  type: string;
  title: string;
  config: Record<string, unknown>;
}

export interface ExpertiseRecord {
  id: string;
  domain: string;
  topic: string;
  summary: string;
  confidence: number;
  source_conversations: string[];
  created_at: string;
}

export interface Contradiction {
  id: string;
  statement_a: string;
  statement_b: string;
  topic: string;
  severity: "low" | "medium" | "high";
  resolved: boolean;
  resolution?: string;
}

export type SearchMode = "hybrid" | "semantic" | "keyword";
export type SortBy = "relevance" | "date_newest" | "date_oldest" | "messages";
export type DateFilter = "" | "today" | "week" | "month" | "custom";
export type ThemeMode = "light" | "dark" | "auto";
