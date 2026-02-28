"""
Constants and default values for Searchat.

Centralizes magic numbers and strings to improve maintainability.
"""
from __future__ import annotations

from pathlib import Path

# ============================================================================
# Application Metadata
# ============================================================================

APP_NAME = "searchat"
APP_VERSION = "0.6.2"
CONFIG_DIR_NAME = ".searchat"

# ============================================================================
# Path Defaults
# ============================================================================

# Default Claude conversation directory name
CLAUDE_DIR_NAME = ".claude"
CLAUDE_PROJECTS_SUBDIR = "projects"

# Default data directory patterns
DEFAULT_DATA_DIR = Path.home() / CONFIG_DIR_NAME
DEFAULT_CONFIG_SUBDIR = "config"
DEFAULT_DATA_SUBDIR = "data"
DEFAULT_LOGS_SUBDIR = "logs"

# Config file names
SETTINGS_FILE = "settings.toml"
DEFAULT_SETTINGS_FILE = "settings.default.toml"
ENV_FILE = ".env"

# ============================================================================
# Web Server Defaults
# ============================================================================

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000
PORT_SCAN_RANGE = (8000, 8010)  # Will try ports in this range

# ============================================================================
# Connector / Tool Names
# ============================================================================

VALID_TOOL_NAMES: frozenset[str] = frozenset({
    "claude", "vibe", "opencode", "codex",
    "gemini", "continue", "cursor", "aider",
})

# ============================================================================
# Search & Indexing Defaults
# ============================================================================

# Embedding model
DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
DEFAULT_EMBEDDING_BATCH_SIZE = 32

# Text chunking
DEFAULT_CHUNK_SIZE = 1500
DEFAULT_CHUNK_OVERLAP = 200

# Indexing
DEFAULT_INDEX_BATCH_SIZE = 1000
DEFAULT_MAX_WORKERS = 4
DEFAULT_AUTO_INDEX = True
DEFAULT_INDEX_INTERVAL_MINUTES = 60
DEFAULT_REINDEX_ON_MODIFICATION = True
DEFAULT_MODIFICATION_DEBOUNCE_MINUTES = 5
DEFAULT_ENABLE_CONNECTORS = True
DEFAULT_ENABLE_ADAPTIVE_INDEXING = True

# Search
DEFAULT_SEARCH_MODE = "hybrid"
DEFAULT_MAX_RESULTS = 100
DEFAULT_SNIPPET_LENGTH = 200

# Temporal scoring
DEFAULT_TEMPORAL_DECAY_ENABLED = False
DEFAULT_TEMPORAL_DECAY_FACTOR = 0.001
DEFAULT_TEMPORAL_WEIGHT = 1.0

# Index metadata versions
INDEX_SCHEMA_VERSION = "1.2"
INDEX_FORMAT_VERSION = "1.0"
INDEX_FORMAT = "parquet+faiss"
INDEX_METADATA_FILENAME = "index_metadata.json"

# ============================================================================
# Performance Defaults
# ============================================================================

DEFAULT_MEMORY_LIMIT_MB = 3000
DEFAULT_QUERY_CACHE_SIZE = 100
DEFAULT_ENABLE_PROFILING = False
DEFAULT_FAISS_MMAP = False

# =========================================================================
# Analytics Defaults
# =========================================================================

DEFAULT_ANALYTICS_ENABLED = False
DEFAULT_ANALYTICS_RETENTION_DAYS = 30

# Chat feature flags
DEFAULT_ENABLE_RAG_CHAT = True
DEFAULT_ENABLE_CHAT_CITATIONS = True

# Export feature flags
DEFAULT_ENABLE_EXPORT_IPYNB = False
DEFAULT_ENABLE_EXPORT_PDF = False
DEFAULT_ENABLE_EXPORT_TECH_DOCS = False

# Dashboards feature flag
DEFAULT_ENABLE_DASHBOARDS = True

# Snapshots feature flag
DEFAULT_ENABLE_SNAPSHOTS = True

# Knowledge graph defaults
DEFAULT_KG_ENABLED = True
DEFAULT_KG_SIMILARITY_THRESHOLD = 0.75
DEFAULT_KG_CONTRADICTION_THRESHOLD = 0.70
DEFAULT_KG_NLI_MODEL = "cross-encoder/nli-deberta-v3-xsmall"

# Expertise store defaults
DEFAULT_EXPERTISE_ENABLED = True
DEFAULT_EXPERTISE_AUTO_EXTRACT = False
DEFAULT_EXPERTISE_PRIME_TOKENS = 4000
DEFAULT_EXPERTISE_DEDUP_THRESHOLD = 0.95
DEFAULT_EXPERTISE_DEDUP_FLAG_THRESHOLD = 0.80

# Expertise staleness / pruning defaults
DEFAULT_EXPERTISE_STALENESS_THRESHOLD = 0.85
DEFAULT_EXPERTISE_MIN_AGE_DAYS = 30
DEFAULT_EXPERTISE_MIN_VALIDATION_COUNT = 0
DEFAULT_EXPERTISE_EXCLUDE_TYPES = "boundary"
DEFAULT_EXPERTISE_PRUNING_ENABLED = True
DEFAULT_EXPERTISE_PRUNING_DRY_RUN = False

# ============================================================================
# UI Defaults
# ============================================================================

DEFAULT_THEME = "auto"
DEFAULT_FONT_FAMILY = "Segoe UI"
DEFAULT_FONT_SIZE = 11
DEFAULT_HIGHLIGHT_COLOR = "#FFEB3B"

# ============================================================================
# Platform Detection
# ============================================================================

# Common Claude directory locations by platform
CLAUDE_DIR_CANDIDATES = [
    Path.home() / CLAUDE_DIR_NAME / CLAUDE_PROJECTS_SUBDIR,  # Standard location
    Path.home() / CLAUDE_DIR_NAME,  # Fallback
]

# OpenCode directory locations by platform  
OPENCODE_DIR_CANDIDATES = [
    Path.home() / ".local" / "share" / "opencode",
]

# OpenAI Codex directory locations
CODEX_DIR_CANDIDATES = [
    Path.home() / ".codex",
]

# Google Gemini CLI directory locations
GEMINI_TMP_DIR_CANDIDATES = [
    Path.home() / ".gemini" / "tmp",
]

# Continue session directory locations
CONTINUE_SESSIONS_DIR_CANDIDATES = [
    Path.home() / ".continue" / "sessions",
]

# WSL mount point patterns
WSL_MOUNT_PREFIX = "/mnt/"
WSL_UNC_PREFIX = "\\\\wsl$\\"

# ============================================================================
# Environment Variable Names
# ============================================================================

ENV_DATA_DIR = "SEARCHAT_DATA_DIR"
ENV_WINDOWS_PROJECTS = "SEARCHAT_WINDOWS_PROJECTS_DIR"
ENV_WSL_PROJECTS = "SEARCHAT_WSL_PROJECTS_DIR"
ENV_ADDITIONAL_DIRS = "SEARCHAT_ADDITIONAL_DIRS"
ENV_OPENCODE_DATA_DIR = "SEARCHAT_OPENCODE_DATA_DIR"
ENV_CODEX_DATA_DIR = "SEARCHAT_CODEX_DATA_DIR"
ENV_GEMINI_DATA_DIR = "SEARCHAT_GEMINI_DATA_DIR"
ENV_CONTINUE_DATA_DIR = "SEARCHAT_CONTINUE_DATA_DIR"
ENV_CURSOR_DATA_DIR = "SEARCHAT_CURSOR_DATA_DIR"
ENV_AIDER_PROJECT_DIRS = "SEARCHAT_AIDER_PROJECT_DIRS"

ENV_PORT = "SEARCHAT_PORT"
ENV_HOST = "SEARCHAT_HOST"

ENV_MEMORY_LIMIT = "SEARCHAT_MEMORY_LIMIT_MB"
ENV_EMBEDDING_MODEL = "SEARCHAT_EMBEDDING_MODEL"
ENV_EMBEDDING_BATCH = "SEARCHAT_EMBEDDING_BATCH_SIZE"
ENV_CACHE_SIZE = "SEARCHAT_QUERY_CACHE_SIZE"
ENV_PROFILING = "SEARCHAT_ENABLE_PROFILING"
ENV_ENABLE_CONNECTORS = "SEARCHAT_ENABLE_CONNECTORS"
ENV_ENABLE_ADAPTIVE_INDEXING = "SEARCHAT_ENABLE_ADAPTIVE_INDEXING"

ENV_ENABLE_ANALYTICS = "SEARCHAT_ENABLE_ANALYTICS"
ENV_ANALYTICS_RETENTION_DAYS = "SEARCHAT_ANALYTICS_RETENTION_DAYS"

ENV_ENABLE_RAG_CHAT = "SEARCHAT_ENABLE_RAG_CHAT"
ENV_ENABLE_CHAT_CITATIONS = "SEARCHAT_ENABLE_CHAT_CITATIONS"

ENV_ENABLE_EXPORT_IPYNB = "SEARCHAT_ENABLE_EXPORT_IPYNB"
ENV_ENABLE_EXPORT_PDF = "SEARCHAT_ENABLE_EXPORT_PDF"
ENV_ENABLE_EXPORT_TECH_DOCS = "SEARCHAT_ENABLE_EXPORT_TECH_DOCS"

ENV_ENABLE_DASHBOARDS = "SEARCHAT_ENABLE_DASHBOARDS"

ENV_ENABLE_SNAPSHOTS = "SEARCHAT_ENABLE_SNAPSHOTS"

# Expertise store
ENV_EXPERTISE_ENABLED = "SEARCHAT_EXPERTISE_ENABLED"
ENV_EXPERTISE_AUTO_EXTRACT = "SEARCHAT_EXPERTISE_AUTO_EXTRACT"
ENV_EXPERTISE_PRIME_TOKENS = "SEARCHAT_EXPERTISE_PRIME_TOKENS"
ENV_EXPERTISE_STALENESS_THRESHOLD = "SEARCHAT_EXPERTISE_STALENESS_THRESHOLD"
ENV_EXPERTISE_MIN_AGE_DAYS = "SEARCHAT_EXPERTISE_MIN_AGE_DAYS"
ENV_EXPERTISE_MIN_VALIDATION_COUNT = "SEARCHAT_EXPERTISE_MIN_VALIDATION_COUNT"
ENV_EXPERTISE_EXCLUDE_TYPES = "SEARCHAT_EXPERTISE_EXCLUDE_TYPES"
ENV_EXPERTISE_PRUNING_ENABLED = "SEARCHAT_EXPERTISE_PRUNING_ENABLED"
ENV_EXPERTISE_PRUNING_DRY_RUN = "SEARCHAT_EXPERTISE_PRUNING_DRY_RUN"

# Knowledge graph
ENV_KG_ENABLED = "SEARCHAT_KG_ENABLED"
ENV_KG_SIMILARITY_THRESHOLD = "SEARCHAT_KG_SIMILARITY_THRESHOLD"
ENV_KG_CONTRADICTION_THRESHOLD = "SEARCHAT_KG_CONTRADICTION_THRESHOLD"
ENV_KG_NLI_MODEL = "SEARCHAT_KG_NLI_MODEL"

ENV_ISOLATION_MODE = "SEARCHAT_ISOLATION_MODE"
ENV_VARIANT_SUFFIX = "SEARCHAT_VARIANT_SUFFIX"

# Embedded LLM (Phase 3)
ENV_LLM_EMBEDDED_MODEL_PATH = "SEARCHAT_LLM_EMBEDDED_MODEL_PATH"
ENV_LLM_EMBEDDED_N_CTX = "SEARCHAT_LLM_EMBEDDED_N_CTX"
ENV_LLM_EMBEDDED_N_THREADS = "SEARCHAT_LLM_EMBEDDED_N_THREADS"
ENV_LLM_EMBEDDED_AUTO_DOWNLOAD = "SEARCHAT_LLM_EMBEDDED_AUTO_DOWNLOAD"
ENV_LLM_EMBEDDED_DEFAULT_PRESET = "SEARCHAT_LLM_EMBEDDED_DEFAULT_PRESET"

# Ghost daemon
ENV_DAEMON_ENABLED = "SEARCHAT_DAEMON_ENABLED"
ENV_DAEMON_POLL_SECONDS = "SEARCHAT_DAEMON_POLL_SECONDS"
ENV_DAEMON_RESCAN_SECONDS = "SEARCHAT_DAEMON_RESCAN_SECONDS"
ENV_DAEMON_NOTIFICATIONS_ENABLED = "SEARCHAT_DAEMON_NOTIFICATIONS_ENABLED"
ENV_DAEMON_NOTIFICATIONS_BACKEND = "SEARCHAT_DAEMON_NOTIFICATIONS_BACKEND"
ENV_DAEMON_MAX_SUGGESTIONS = "SEARCHAT_DAEMON_MAX_SUGGESTIONS"
ENV_DAEMON_MIN_QUERY_LENGTH = "SEARCHAT_DAEMON_MIN_QUERY_LENGTH"

# ============================================================================
# RAG System Prompt
# ============================================================================

RAG_SYSTEM_PROMPT = """You are an intelligent knowledge assistant for a developer's personal archives.
You will be provided with "Context Chunks" retrieved from the user's past chat history.

**Instructions:**
1. Answer the user's question *only* using the provided Context Chunks.
2. If the answer is not in the chunks, state that you cannot find the information in the archives. Do not hallucinate.
3. **Citations:** When you state a fact, reference the date or conversation ID from the chunk (e.g., "[Date: 2023-10-12]" or "[Source: ID_123]").
4. Be concise and technical. The user is a developer.

**Context Chunks:**
{context_data}""".strip()

# ============================================================================
# DuckDB Full-Text Search
# ============================================================================

FTS_STEMMER = "english"
FTS_STOPWORDS = "english"

# ============================================================================
# CORS / Server Defaults
# ============================================================================

DEFAULT_CORS_ORIGINS: list[str] = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# ============================================================================
# Re-ranking Defaults
# ============================================================================

DEFAULT_RERANKING_ENABLED = False
DEFAULT_RERANKING_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
DEFAULT_RERANKING_TOP_K = 50

# Environment variable names for re-ranking
ENV_RERANKING_ENABLED = "SEARCHAT_RERANKING_ENABLED"
ENV_RERANKING_MODEL = "SEARCHAT_RERANKING_MODEL"
ENV_RERANKING_TOP_K = "SEARCHAT_RERANKING_TOP_K"

# Environment variable for CORS
ENV_CORS_ORIGINS = "SEARCHAT_CORS_ORIGINS"

# ============================================================================
# Query Expansion / Synonyms
# ============================================================================

QUERY_SYNONYMS: dict[str, list[str]] = {
    "auth": ["authentication", "authorization"],
    "db": ["database"],
    "config": ["configuration"],
    "env": ["environment"],
    "deps": ["dependencies"],
    "repo": ["repository"],
    "impl": ["implementation"],
    "func": ["function"],
    "arg": ["argument"],
    "param": ["parameter"],
}

# ============================================================================
# Pattern Mining
# ============================================================================

PATTERN_MINING_SEEDS: list[str] = [
    "coding conventions",
    "architecture decisions",
    "best practices",
    "recurring patterns",
    "project rules",
]

# ============================================================================
# Agent Config Templates
# ============================================================================

AGENT_CONFIG_TEMPLATES: dict[str, str] = {
    "claude.md": "# {project_name} — CLAUDE.md\n\n## Conventions\n\n{patterns}\n",
    "copilot-instructions.md": "# {project_name} — Copilot Instructions\n\n{patterns}\n",
    "cursorrules": "# {project_name}\n\n{patterns}\n",
}

# ============================================================================
# Error Messages
# ============================================================================

ERROR_NO_CONFIG = """
Configuration file not found: {path}

Run the setup wizard to create configuration:
    python -m searchat.setup

Or manually copy the example config:
    mkdir -p {config_dir}
    cp config/{default_file} {config_dir}/{settings_file}
    cp .env.example {config_dir}/.env
"""

ERROR_NO_CLAUDE_DIR = """
Claude conversation directory not found.

Searched locations:
{locations}

Please ensure Claude CLI is installed and has created conversations, or
specify the directory manually in {config_file}
"""

ERROR_INVALID_PORT = """
Invalid port number: {port}

Port must be between 1 and 65535.
"""

ERROR_PORT_IN_USE = """
All ports in range {start}-{end} are in use.

Try:
1. Stop other services using these ports
2. Specify a different port: SEARCHAT_PORT=9000 searchat-web
3. Check for zombie processes: netstat -ano | findstr :{port}
"""
