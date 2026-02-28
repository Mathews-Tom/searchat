"""
Configuration management with environment variable and .env support.

Configuration precedence (highest to lowest):
1. Environment variables (SEARCHAT_*)
2. User config file (~/.searchat/config/settings.toml)
3. Default config file (./config/settings.default.toml)
4. Hardcoded constants (constants.py)
"""

from __future__ import annotations

import os
from typing import overload
from dataclasses import dataclass
from pathlib import Path
import tomli
from dotenv import load_dotenv

from ..core.logging_config import LogConfig
from .constants import (
    DEFAULT_DATA_DIR,
    DEFAULT_CONFIG_SUBDIR,
    SETTINGS_FILE,
    DEFAULT_SETTINGS_FILE,
    ENV_FILE,
    # Defaults
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_EMBEDDING_BATCH_SIZE,
    DEFAULT_INDEX_BATCH_SIZE,
    DEFAULT_MAX_WORKERS,
    DEFAULT_AUTO_INDEX,
    DEFAULT_INDEX_INTERVAL_MINUTES,
    DEFAULT_REINDEX_ON_MODIFICATION,
    DEFAULT_MODIFICATION_DEBOUNCE_MINUTES,
    DEFAULT_ENABLE_CONNECTORS,
    DEFAULT_ENABLE_ADAPTIVE_INDEXING,
    DEFAULT_SEARCH_MODE,
    DEFAULT_MAX_RESULTS,
    DEFAULT_SNIPPET_LENGTH,
    DEFAULT_TEMPORAL_DECAY_ENABLED,
    DEFAULT_TEMPORAL_DECAY_FACTOR,
    DEFAULT_TEMPORAL_WEIGHT,
    DEFAULT_MEMORY_LIMIT_MB,
    DEFAULT_QUERY_CACHE_SIZE,
    DEFAULT_ENABLE_PROFILING,
    DEFAULT_FAISS_MMAP,
    DEFAULT_ANALYTICS_ENABLED,
    DEFAULT_ANALYTICS_RETENTION_DAYS,
    DEFAULT_ENABLE_RAG_CHAT,
    DEFAULT_ENABLE_CHAT_CITATIONS,
    DEFAULT_ENABLE_EXPORT_IPYNB,
    DEFAULT_ENABLE_EXPORT_PDF,
    DEFAULT_ENABLE_EXPORT_TECH_DOCS,
    DEFAULT_ENABLE_DASHBOARDS,
    DEFAULT_ENABLE_SNAPSHOTS,
    DEFAULT_THEME,
    DEFAULT_FONT_FAMILY,
    DEFAULT_FONT_SIZE,
    DEFAULT_HIGHLIGHT_COLOR,
    DEFAULT_CORS_ORIGINS,
    DEFAULT_RERANKING_ENABLED,
    DEFAULT_RERANKING_MODEL,
    DEFAULT_RERANKING_TOP_K,
    # Environment variable names
    ENV_DATA_DIR,
    ENV_WINDOWS_PROJECTS,
    ENV_WSL_PROJECTS,
    ENV_MEMORY_LIMIT,
    ENV_EMBEDDING_MODEL,
    ENV_EMBEDDING_BATCH,
    ENV_CACHE_SIZE,
    ENV_PROFILING,
    ENV_ENABLE_CONNECTORS,
    ENV_ENABLE_ADAPTIVE_INDEXING,
    ENV_ENABLE_ANALYTICS,
    ENV_ANALYTICS_RETENTION_DAYS,
    ENV_ENABLE_RAG_CHAT,
    ENV_ENABLE_CHAT_CITATIONS,
    ENV_ENABLE_EXPORT_IPYNB,
    ENV_ENABLE_EXPORT_PDF,
    ENV_ENABLE_EXPORT_TECH_DOCS,
    ENV_ENABLE_DASHBOARDS,
    ENV_ENABLE_SNAPSHOTS,
    ENV_LLM_EMBEDDED_MODEL_PATH,
    ENV_LLM_EMBEDDED_N_CTX,
    ENV_LLM_EMBEDDED_N_THREADS,
    ENV_LLM_EMBEDDED_AUTO_DOWNLOAD,
    ENV_LLM_EMBEDDED_DEFAULT_PRESET,
    ENV_DAEMON_ENABLED,
    ENV_DAEMON_POLL_SECONDS,
    ENV_DAEMON_RESCAN_SECONDS,
    ENV_DAEMON_NOTIFICATIONS_ENABLED,
    ENV_DAEMON_NOTIFICATIONS_BACKEND,
    ENV_DAEMON_MAX_SUGGESTIONS,
    ENV_DAEMON_MIN_QUERY_LENGTH,
    ENV_CORS_ORIGINS,
    ENV_RERANKING_ENABLED,
    ENV_RERANKING_MODEL,
    ENV_RERANKING_TOP_K,
    ERROR_NO_CONFIG,
    DEFAULT_EXPERTISE_ENABLED,
    DEFAULT_EXPERTISE_AUTO_EXTRACT,
    DEFAULT_EXPERTISE_PRIME_TOKENS,
    DEFAULT_EXPERTISE_DEDUP_THRESHOLD,
    DEFAULT_EXPERTISE_DEDUP_FLAG_THRESHOLD,
    DEFAULT_EXPERTISE_STALENESS_THRESHOLD,
    DEFAULT_EXPERTISE_MIN_AGE_DAYS,
    DEFAULT_EXPERTISE_MIN_VALIDATION_COUNT,
    DEFAULT_EXPERTISE_EXCLUDE_TYPES,
    DEFAULT_EXPERTISE_PRUNING_ENABLED,
    DEFAULT_EXPERTISE_PRUNING_DRY_RUN,
    ENV_EXPERTISE_ENABLED,
    ENV_EXPERTISE_AUTO_EXTRACT,
    ENV_EXPERTISE_PRIME_TOKENS,
    ENV_EXPERTISE_STALENESS_THRESHOLD,
    ENV_EXPERTISE_MIN_AGE_DAYS,
    ENV_EXPERTISE_MIN_VALIDATION_COUNT,
    ENV_EXPERTISE_EXCLUDE_TYPES,
    ENV_EXPERTISE_PRUNING_ENABLED,
    ENV_EXPERTISE_PRUNING_DRY_RUN,
)


# Load .env file at module import time
# Search order: ./.env, ~/.searchat/.env, ~/.searchat/config/.env
def _load_env_files():
    """Load .env files from standard locations."""
    env_locations = [
        Path.cwd() / ENV_FILE,  # Project root
        DEFAULT_DATA_DIR / ENV_FILE,  # Data directory
        DEFAULT_DATA_DIR / DEFAULT_CONFIG_SUBDIR / ENV_FILE,  # Config directory
    ]

    for env_path in env_locations:
        if env_path.exists():
            load_dotenv(env_path, override=False)  # Don't override already-set vars


_load_env_files()


@overload
def _get_env_str(key: str, default: str) -> str: ...


@overload
def _get_env_str(key: str, default: None = None) -> str | None: ...


def _get_env_str(key: str, default: str | None = None) -> str | None:
    """Get string value from environment variable. Empty strings are treated as missing."""
    value = os.getenv(key)
    if value is None or value == "":
        return default
    return value


def _get_env_int(key: str, default: int) -> int:
    """Get integer value from environment variable."""
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_env_bool(key: str, default: bool) -> bool:
    """Get boolean value from environment variable."""
    value = os.getenv(key)
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes", "on")


def _get_env_float(key: str, default: float) -> float:
    """Get float value from environment variable."""
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass
class PathsConfig:
    claude_directory_windows: str
    claude_directory_wsl: str
    search_directory: str
    auto_detect_environment: bool

    @classmethod
    def from_dict(cls, data: dict) -> "PathsConfig":
        """Create PathsConfig from dict with environment variable overrides."""
        return cls(
            claude_directory_windows=_get_env_str(
                ENV_WINDOWS_PROJECTS,
                data.get("claude_directory_windows", "C:/Users/{username}/.claude")
            ) or "C:/Users/{username}/.claude",
            claude_directory_wsl=_get_env_str(
                ENV_WSL_PROJECTS,
                data.get("claude_directory_wsl", "")
            ) or "",
            search_directory=_get_env_str(
                ENV_DATA_DIR,
                data.get("search_directory", str(DEFAULT_DATA_DIR))
            ) or str(DEFAULT_DATA_DIR),
            auto_detect_environment=_get_env_bool(
                "SEARCHAT_AUTO_DETECT",
                data.get("auto_detect_environment", True)
            ),
        )


@dataclass
class IndexingConfig:
    batch_size: int
    auto_index: bool
    index_interval_minutes: int
    max_workers: int
    reindex_on_modification: bool
    modification_debounce_minutes: int
    enable_connectors: bool
    enable_adaptive_indexing: bool

    @classmethod
    def from_dict(cls, data: dict) -> "IndexingConfig":
        """Create IndexingConfig from dict with environment variable overrides."""
        return cls(
            batch_size=_get_env_int(
                "SEARCHAT_INDEX_BATCH_SIZE",
                data.get("batch_size", DEFAULT_INDEX_BATCH_SIZE)
            ),
            auto_index=_get_env_bool(
                "SEARCHAT_AUTO_INDEX",
                data.get("auto_index", DEFAULT_AUTO_INDEX)
            ),
            index_interval_minutes=_get_env_int(
                "SEARCHAT_INDEX_INTERVAL",
                data.get("index_interval_minutes", DEFAULT_INDEX_INTERVAL_MINUTES)
            ),
            max_workers=_get_env_int(
                "SEARCHAT_MAX_WORKERS",
                data.get("max_workers", DEFAULT_MAX_WORKERS)
            ),
            reindex_on_modification=_get_env_bool(
                "SEARCHAT_REINDEX_ON_MODIFICATION",
                data.get("reindex_on_modification", DEFAULT_REINDEX_ON_MODIFICATION)
            ),
            modification_debounce_minutes=_get_env_int(
                "SEARCHAT_MODIFICATION_DEBOUNCE_MINUTES",
                data.get("modification_debounce_minutes", DEFAULT_MODIFICATION_DEBOUNCE_MINUTES)
            ),
            enable_connectors=_get_env_bool(
                ENV_ENABLE_CONNECTORS,
                data.get("enable_connectors", DEFAULT_ENABLE_CONNECTORS)
            ),
            enable_adaptive_indexing=_get_env_bool(
                ENV_ENABLE_ADAPTIVE_INDEXING,
                data.get("enable_adaptive_indexing", DEFAULT_ENABLE_ADAPTIVE_INDEXING)
            ),
        )


@dataclass
class SearchConfig:
    default_mode: str
    max_results: int
    snippet_length: int
    temporal_decay_enabled: bool
    temporal_decay_factor: float
    temporal_weight: float

    @classmethod
    def from_dict(cls, data: dict) -> "SearchConfig":
        """Create SearchConfig from dict with environment variable overrides."""
        return cls(
            default_mode=_get_env_str(
                "SEARCHAT_DEFAULT_MODE",
                data.get("default_mode", DEFAULT_SEARCH_MODE)
            ) or DEFAULT_SEARCH_MODE,
            max_results=_get_env_int(
                "SEARCHAT_MAX_RESULTS",
                data.get("max_results", DEFAULT_MAX_RESULTS)
            ),
            snippet_length=_get_env_int(
                "SEARCHAT_SNIPPET_LENGTH",
                data.get("snippet_length", DEFAULT_SNIPPET_LENGTH)
            ),
            temporal_decay_enabled=_get_env_bool(
                "SEARCHAT_TEMPORAL_DECAY_ENABLED",
                bool(data.get("temporal_decay_enabled", DEFAULT_TEMPORAL_DECAY_ENABLED)),
            ),
            temporal_decay_factor=_get_env_float(
                "SEARCHAT_TEMPORAL_DECAY_FACTOR",
                float(data.get("temporal_decay_factor", DEFAULT_TEMPORAL_DECAY_FACTOR)),
            ),
            temporal_weight=_get_env_float(
                "SEARCHAT_TEMPORAL_WEIGHT",
                float(data.get("temporal_weight", DEFAULT_TEMPORAL_WEIGHT)),
            ),
        )


@dataclass
class EmbeddingConfig:
    model: str
    batch_size: int
    cache_embeddings: bool
    device: str = "auto"  # auto, cuda, cpu

    @classmethod
    def from_dict(cls, data: dict) -> "EmbeddingConfig":
        """Create EmbeddingConfig from dict with environment variable overrides."""
        return cls(
            model=_get_env_str(
                ENV_EMBEDDING_MODEL,
                data.get("model", DEFAULT_EMBEDDING_MODEL)
            ) or DEFAULT_EMBEDDING_MODEL,
            batch_size=_get_env_int(
                ENV_EMBEDDING_BATCH,
                data.get("batch_size", DEFAULT_EMBEDDING_BATCH_SIZE)
            ),
            cache_embeddings=_get_env_bool(
                "SEARCHAT_CACHE_EMBEDDINGS",
                data.get("cache_embeddings", True)
            ),
            device=_get_env_str(
                "SEARCHAT_EMBEDDING_DEVICE",
                data.get("device", "auto")
            ) or "auto",
        )

    def get_device(self) -> str:
        """
        Get the actual device to use (resolves 'auto' to cuda/mps/cpu).

        Priority order:
        1. CUDA (NVIDIA GPUs) - Windows, Linux
        2. MPS (Apple Silicon) - macOS M1/M2/M3
        3. CPU (fallback)
        """
        if self.device == "auto":
            try:
                import torch
                # Check CUDA first (NVIDIA GPUs on Windows/Linux)
                if torch.cuda.is_available():
                    return "cuda"
                # Check MPS (Apple Silicon on macOS)
                if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                    return "mps"
                # Fallback to CPU
                return "cpu"
            except ImportError:
                return "cpu"
        return self.device


@dataclass
class LLMConfig:
    default_provider: str
    openai_model: str | None
    ollama_model: str | None
    embedded_model_path: str | None
    embedded_n_ctx: int
    embedded_n_threads: int
    embedded_auto_download: bool
    embedded_default_preset: str

    @classmethod
    def from_dict(cls, data: dict) -> "LLMConfig":
        """Create LLMConfig from dict with environment variable overrides."""
        return cls(
            default_provider=_get_env_str(
                "SEARCHAT_LLM_PROVIDER",
                data.get("default_provider", "ollama"),
            ) or "ollama",
            openai_model=_get_env_str(
                "SEARCHAT_LLM_OPENAI_MODEL",
                data.get("openai_model"),
            ),
            ollama_model=_get_env_str(
                "SEARCHAT_LLM_OLLAMA_MODEL",
                data.get("ollama_model"),
            ),
            embedded_model_path=_get_env_str(
                ENV_LLM_EMBEDDED_MODEL_PATH,
                data.get("embedded_model_path") or None,
            ),
            embedded_n_ctx=_get_env_int(
                ENV_LLM_EMBEDDED_N_CTX,
                int(data.get("embedded_n_ctx", 4096)),
            ),
            embedded_n_threads=_get_env_int(
                ENV_LLM_EMBEDDED_N_THREADS,
                int(data.get("embedded_n_threads", 0)),
            ),
            embedded_auto_download=_get_env_bool(
                ENV_LLM_EMBEDDED_AUTO_DOWNLOAD,
                bool(data.get("embedded_auto_download", True)),
            ),
            embedded_default_preset=_get_env_str(
                ENV_LLM_EMBEDDED_DEFAULT_PRESET,
                data.get("embedded_default_preset", "qwen2.5-coder-1.5b-instruct-q4_k_m"),
            )
            or "qwen2.5-coder-1.5b-instruct-q4_k_m",
        )


@dataclass
class UIConfig:
    theme: str
    font_family: str
    font_size: int
    highlight_color: str

    @classmethod
    def from_dict(cls, data: dict) -> "UIConfig":
        """Create UIConfig from dict with environment variable overrides."""
        return cls(
            theme=_get_env_str(
                "SEARCHAT_THEME",
                data.get("theme", DEFAULT_THEME)
            ) or DEFAULT_THEME,
            font_family=_get_env_str(
                "SEARCHAT_FONT_FAMILY",
                data.get("font_family", DEFAULT_FONT_FAMILY)
            ) or DEFAULT_FONT_FAMILY,
            font_size=_get_env_int(
                "SEARCHAT_FONT_SIZE",
                data.get("font_size", DEFAULT_FONT_SIZE)
            ),
            highlight_color=_get_env_str(
                "SEARCHAT_HIGHLIGHT_COLOR",
                data.get("highlight_color", DEFAULT_HIGHLIGHT_COLOR)
            ) or DEFAULT_HIGHLIGHT_COLOR,
        )


@dataclass
class PerformanceConfig:
    memory_limit_mb: int
    query_cache_size: int
    enable_profiling: bool
    faiss_mmap: bool

    @classmethod
    def from_dict(cls, data: dict) -> "PerformanceConfig":
        """Create PerformanceConfig from dict with environment variable overrides."""
        return cls(
            memory_limit_mb=_get_env_int(
                ENV_MEMORY_LIMIT,
                data.get("memory_limit_mb", DEFAULT_MEMORY_LIMIT_MB)
            ),
            query_cache_size=_get_env_int(
                ENV_CACHE_SIZE,
                data.get("query_cache_size", DEFAULT_QUERY_CACHE_SIZE)
            ),
            enable_profiling=_get_env_bool(
                ENV_PROFILING,
                data.get("enable_profiling", DEFAULT_ENABLE_PROFILING)
            ),
            faiss_mmap=_get_env_bool(
                "SEARCHAT_FAISS_MMAP",
                bool(data.get("faiss_mmap", DEFAULT_FAISS_MMAP)),
            ),
        )


@dataclass
class AnalyticsConfig:
    enabled: bool
    retention_days: int

    @classmethod
    def from_dict(cls, data: dict) -> "AnalyticsConfig":
        return cls(
            enabled=_get_env_bool(
                ENV_ENABLE_ANALYTICS,
                data.get("enabled", DEFAULT_ANALYTICS_ENABLED),
            ),
            retention_days=_get_env_int(
                ENV_ANALYTICS_RETENTION_DAYS,
                data.get("retention_days", DEFAULT_ANALYTICS_RETENTION_DAYS),
            ),
        )


@dataclass
class ChatConfig:
    enable_rag: bool
    enable_citations: bool

    @classmethod
    def from_dict(cls, data: dict) -> "ChatConfig":
        return cls(
            enable_rag=_get_env_bool(
                ENV_ENABLE_RAG_CHAT,
                data.get("enable_rag", DEFAULT_ENABLE_RAG_CHAT),
            ),
            enable_citations=_get_env_bool(
                ENV_ENABLE_CHAT_CITATIONS,
                data.get("enable_citations", DEFAULT_ENABLE_CHAT_CITATIONS),
            ),
        )


@dataclass
class ExportConfig:
    enable_ipynb: bool
    enable_pdf: bool
    enable_tech_docs: bool

    @classmethod
    def from_dict(cls, data: dict) -> "ExportConfig":
        return cls(
            enable_ipynb=_get_env_bool(
                ENV_ENABLE_EXPORT_IPYNB,
                data.get("enable_ipynb", DEFAULT_ENABLE_EXPORT_IPYNB),
            ),
            enable_pdf=_get_env_bool(
                ENV_ENABLE_EXPORT_PDF,
                data.get("enable_pdf", DEFAULT_ENABLE_EXPORT_PDF),
            ),
            enable_tech_docs=_get_env_bool(
                ENV_ENABLE_EXPORT_TECH_DOCS,
                data.get("enable_tech_docs", DEFAULT_ENABLE_EXPORT_TECH_DOCS),
            ),
        )


@dataclass
class DashboardsConfig:
    enabled: bool

    @classmethod
    def from_dict(cls, data: dict) -> "DashboardsConfig":
        return cls(
            enabled=_get_env_bool(
                ENV_ENABLE_DASHBOARDS,
                data.get("enabled", DEFAULT_ENABLE_DASHBOARDS),
            )
        )


@dataclass
class SnapshotsConfig:
    enabled: bool

    @classmethod
    def from_dict(cls, data: dict) -> "SnapshotsConfig":
        return cls(
            enabled=_get_env_bool(
                ENV_ENABLE_SNAPSHOTS,
                data.get("enabled", DEFAULT_ENABLE_SNAPSHOTS),
            )
        )


@dataclass
class DaemonConfig:
    enabled: bool
    poll_seconds: int
    rescan_seconds: int
    notifications_enabled: bool
    notifications_backend: str
    max_suggestions: int
    min_query_length: int

    @classmethod
    def from_dict(cls, data: dict) -> "DaemonConfig":
        return cls(
            enabled=_get_env_bool(ENV_DAEMON_ENABLED, bool(data.get("enabled", False))),
            poll_seconds=_get_env_int(ENV_DAEMON_POLL_SECONDS, int(data.get("poll_seconds", 5))),
            rescan_seconds=_get_env_int(ENV_DAEMON_RESCAN_SECONDS, int(data.get("rescan_seconds", 30))),
            notifications_enabled=_get_env_bool(
                ENV_DAEMON_NOTIFICATIONS_ENABLED,
                bool(data.get("notifications_enabled", True)),
            ),
            notifications_backend=_get_env_str(
                ENV_DAEMON_NOTIFICATIONS_BACKEND,
                data.get("notifications_backend", "auto"),
            )
            or "auto",
            max_suggestions=_get_env_int(
                ENV_DAEMON_MAX_SUGGESTIONS,
                int(data.get("max_suggestions", 3)),
            ),
            min_query_length=_get_env_int(
                ENV_DAEMON_MIN_QUERY_LENGTH,
                int(data.get("min_query_length", 8)),
            ),
        )


@dataclass
class RerankingConfig:
    enabled: bool
    model: str
    top_k: int

    @classmethod
    def from_dict(cls, data: dict) -> "RerankingConfig":
        return cls(
            enabled=_get_env_bool(
                ENV_RERANKING_ENABLED,
                data.get("enabled", DEFAULT_RERANKING_ENABLED),
            ),
            model=_get_env_str(
                ENV_RERANKING_MODEL,
                data.get("model", DEFAULT_RERANKING_MODEL),
            ) or DEFAULT_RERANKING_MODEL,
            top_k=_get_env_int(
                ENV_RERANKING_TOP_K,
                data.get("top_k", DEFAULT_RERANKING_TOP_K),
            ),
        )


@dataclass
class ExpertiseConfig:
    enabled: bool
    auto_extract: bool
    default_prime_tokens: int
    dedup_similarity_threshold: float
    dedup_flag_threshold: float
    staleness_threshold: float
    min_age_days: int
    min_validation_count: int
    exclude_types: list[str]
    pruning_enabled: bool
    pruning_dry_run: bool

    @classmethod
    def from_dict(cls, data: dict) -> "ExpertiseConfig":
        raw_exclude = _get_env_str(
            ENV_EXPERTISE_EXCLUDE_TYPES,
            data.get("exclude_types", DEFAULT_EXPERTISE_EXCLUDE_TYPES),
        )
        if isinstance(raw_exclude, str):
            exclude_types = [t.strip() for t in raw_exclude.split(",") if t.strip()]
        else:
            exclude_types = list(raw_exclude) if raw_exclude else []

        return cls(
            enabled=_get_env_bool(
                ENV_EXPERTISE_ENABLED,
                data.get("enabled", DEFAULT_EXPERTISE_ENABLED),
            ),
            auto_extract=_get_env_bool(
                ENV_EXPERTISE_AUTO_EXTRACT,
                data.get("auto_extract", DEFAULT_EXPERTISE_AUTO_EXTRACT),
            ),
            default_prime_tokens=_get_env_int(
                ENV_EXPERTISE_PRIME_TOKENS,
                data.get("default_prime_tokens", DEFAULT_EXPERTISE_PRIME_TOKENS),
            ),
            dedup_similarity_threshold=float(
                data.get("dedup_similarity_threshold", DEFAULT_EXPERTISE_DEDUP_THRESHOLD)
            ),
            dedup_flag_threshold=float(
                data.get("dedup_flag_threshold", DEFAULT_EXPERTISE_DEDUP_FLAG_THRESHOLD)
            ),
            staleness_threshold=_get_env_float(
                ENV_EXPERTISE_STALENESS_THRESHOLD,
                float(data.get("staleness_threshold", DEFAULT_EXPERTISE_STALENESS_THRESHOLD)),
            ),
            min_age_days=_get_env_int(
                ENV_EXPERTISE_MIN_AGE_DAYS,
                int(data.get("min_age_days", DEFAULT_EXPERTISE_MIN_AGE_DAYS)),
            ),
            min_validation_count=_get_env_int(
                ENV_EXPERTISE_MIN_VALIDATION_COUNT,
                int(data.get("min_validation_count", DEFAULT_EXPERTISE_MIN_VALIDATION_COUNT)),
            ),
            exclude_types=exclude_types,
            pruning_enabled=_get_env_bool(
                ENV_EXPERTISE_PRUNING_ENABLED,
                bool(data.get("pruning_enabled", DEFAULT_EXPERTISE_PRUNING_ENABLED)),
            ),
            pruning_dry_run=_get_env_bool(
                ENV_EXPERTISE_PRUNING_DRY_RUN,
                bool(data.get("pruning_dry_run", DEFAULT_EXPERTISE_PRUNING_DRY_RUN)),
            ),
        )


@dataclass
class ServerConfig:
    cors_origins: list[str]

    @classmethod
    def from_dict(cls, data: dict) -> "ServerConfig":
        env_origins = _get_env_str(ENV_CORS_ORIGINS, None)
        if env_origins:
            origins = [o.strip() for o in env_origins.split(",") if o.strip()]
        else:
            origins = data.get("cors_origins", list(DEFAULT_CORS_ORIGINS))
        return cls(cors_origins=origins)


@dataclass
class Config:
    paths: PathsConfig
    indexing: IndexingConfig
    search: SearchConfig
    embedding: EmbeddingConfig
    llm: LLMConfig
    ui: UIConfig
    performance: PerformanceConfig
    analytics: AnalyticsConfig
    chat: ChatConfig
    export: ExportConfig
    dashboards: DashboardsConfig
    snapshots: SnapshotsConfig
    daemon: DaemonConfig
    reranking: RerankingConfig
    server: ServerConfig
    expertise: ExpertiseConfig
    logging: LogConfig

    @classmethod
    def load(cls, config_path: Path | None = None) -> "Config":
        """
        Load configuration with proper precedence.

        Precedence (highest to lowest):
        1. Environment variables (SEARCHAT_*)
        2. User config (~/.searchat/config/settings.toml)
        3. Default config (./config/settings.default.toml)
        4. Hardcoded constants

        Args:
            config_path: Optional explicit config file path

        Returns:
            Loaded Config object

        Raises:
            FileNotFoundError: If no config file is found
        """
        # Determine config file locations
        if config_path is not None:
            # Explicit path provided
            config_files = [config_path]
        else:
            # Standard search order
            base_data_dir = Path(os.getenv(ENV_DATA_DIR, str(DEFAULT_DATA_DIR))).expanduser()
            user_config = base_data_dir / DEFAULT_CONFIG_SUBDIR / SETTINGS_FILE
            default_config = Path(__file__).parent.parent / "config" / DEFAULT_SETTINGS_FILE
            config_files = [user_config, default_config]

        # Try to load from config files in order
        data = None
        loaded_from = None

        for config_file in config_files:
            if config_file.exists():
                with open(config_file, "rb") as f:
                    data = tomli.load(f)
                loaded_from = config_file
                break

        # If no config file found, use empty dict (will use constants.py defaults)
        if data is None:
            # Only raise error if an explicit config path was provided
            if config_path is not None:
                raise FileNotFoundError(
                    ERROR_NO_CONFIG.format(
                        path=config_path,
                        config_dir=DEFAULT_DATA_DIR / DEFAULT_CONFIG_SUBDIR,
                        default_file=DEFAULT_SETTINGS_FILE,
                        settings_file=SETTINGS_FILE,
                    )
                )
            # Otherwise, use empty dict and rely on constants.py
            data = {}

        # Build config objects with environment variable overrides
        return cls(
            paths=PathsConfig.from_dict(data.get("paths", {})),
            indexing=IndexingConfig.from_dict(data.get("indexing", {})),
            search=SearchConfig.from_dict(data.get("search", {})),
            embedding=EmbeddingConfig.from_dict(data.get("embedding", {})),
            llm=LLMConfig.from_dict(data.get("llm", {})),
            ui=UIConfig.from_dict(data.get("ui", {})),
            performance=PerformanceConfig.from_dict(data.get("performance", {})),
            analytics=AnalyticsConfig.from_dict(data.get("analytics", {})),
            chat=ChatConfig.from_dict(data.get("chat", {})),
            export=ExportConfig.from_dict(data.get("export", {})),
            dashboards=DashboardsConfig.from_dict(data.get("dashboards", {})),
            snapshots=SnapshotsConfig.from_dict(data.get("snapshots", {})),
            daemon=DaemonConfig.from_dict(data.get("daemon", {})),
            reranking=RerankingConfig.from_dict(data.get("reranking", {})),
            server=ServerConfig.from_dict(data.get("server", {})),
            expertise=ExpertiseConfig.from_dict(data.get("expertise", {})),
            logging=LogConfig(**data.get("logging", {})),
        )
