"""
Constants and default values for Searchat.

Centralizes magic numbers and strings to improve maintainability.
"""

from pathlib import Path

# ============================================================================
# Application Metadata
# ============================================================================

APP_NAME = "searchat"
APP_VERSION = "0.1.0"
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

# Search
DEFAULT_SEARCH_MODE = "hybrid"
DEFAULT_MAX_RESULTS = 100
DEFAULT_SNIPPET_LENGTH = 200

# ============================================================================
# Performance Defaults
# ============================================================================

DEFAULT_MEMORY_LIMIT_MB = 3000
DEFAULT_QUERY_CACHE_SIZE = 100
DEFAULT_ENABLE_PROFILING = False

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

ENV_PORT = "SEARCHAT_PORT"
ENV_HOST = "SEARCHAT_HOST"

ENV_MEMORY_LIMIT = "SEARCHAT_MEMORY_LIMIT_MB"
ENV_EMBEDDING_MODEL = "SEARCHAT_EMBEDDING_MODEL"
ENV_EMBEDDING_BATCH = "SEARCHAT_EMBEDDING_BATCH_SIZE"
ENV_CACHE_SIZE = "SEARCHAT_QUERY_CACHE_SIZE"
ENV_PROFILING = "SEARCHAT_ENABLE_PROFILING"

ENV_ISOLATION_MODE = "SEARCHAT_ISOLATION_MODE"
ENV_VARIANT_SUFFIX = "SEARCHAT_VARIANT_SUFFIX"

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
