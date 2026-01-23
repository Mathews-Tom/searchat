"""
Live file watcher for AI coding agent conversation directories.

Monitors for new/modified conversation files and triggers append-only indexing.

Supported agents:
- Claude Code: ~/.claude/projects/**/*.jsonl
- Mistral Vibe: ~/.vibe/logs/session/*.json
"""

import logging
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set
from queue import Queue, Empty

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent

from searchat.config import PathResolver, Config

logger = logging.getLogger(__name__)


class ConversationEventHandler(FileSystemEventHandler):
    """Handles file system events for conversation files (JSONL and JSON)."""

    # Supported file extensions
    SUPPORTED_EXTENSIONS = ('.jsonl', '.json')

    def __init__(self, pending_queue: Queue, debounce_seconds: float = 2.0):
        super().__init__()
        self.pending_queue = pending_queue
        self.debounce_seconds = debounce_seconds
        self._last_event_times: Dict[str, float] = {}
        self._lock = threading.Lock()

    def _should_process(self, path: str) -> bool:
        """Check if file should be processed (debounce rapid events)."""
        # Check for supported extensions
        if not any(path.endswith(ext) for ext in self.SUPPORTED_EXTENSIONS):
            return False

        current_time = time.time()
        with self._lock:
            last_time = self._last_event_times.get(path, 0)
            if current_time - last_time < self.debounce_seconds:
                return False
            self._last_event_times[path] = current_time
            return True

    def on_created(self, event):
        if event.is_directory:
            return
        if self._should_process(event.src_path):
            logger.info(f"New conversation detected: {event.src_path}")
            self.pending_queue.put(('created', event.src_path))

    def on_modified(self, event):
        if event.is_directory:
            return
        if self._should_process(event.src_path):
            logger.info(f"Conversation modified: {event.src_path}")
            self.pending_queue.put(('modified', event.src_path))


class ConversationWatcher:
    """
    Watches AI coding agent conversation directories for changes.

    Supported agents:
    - Claude Code: ~/.claude/projects/
    - Mistral Vibe: ~/.vibe/logs/session/

    Triggers append-only indexing when new or modified files are detected.
    Does NOT trigger on file deletions (preserves orphaned data).
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        on_update: Optional[Callable[[List[str]], None]] = None,
        batch_delay_seconds: float = 5.0,
        debounce_seconds: float = 2.0,
    ):
        """
        Initialize the conversation watcher.

        Args:
            config: Configuration object
            on_update: Callback when files need indexing (receives list of paths)
            batch_delay_seconds: Wait time before processing batched updates
            debounce_seconds: Minimum time between events for same file
        """
        if config is None:
            config = Config.load()
        self.config = config

        self.path_resolver = PathResolver()
        self.claude_dirs = self.path_resolver.resolve_claude_dirs(config)
        self.vibe_dirs = self.path_resolver.resolve_vibe_dirs()

        # Combine all watched directories
        self.watched_dirs = self.claude_dirs + self.vibe_dirs

        self.on_update = on_update
        self.batch_delay_seconds = batch_delay_seconds
        self.debounce_seconds = debounce_seconds

        self._pending_queue: Queue = Queue()
        self._observer: Optional[Observer] = None
        self._processor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False

        # Track indexed files to detect truly new ones
        self._indexed_files: Set[str] = set()

        # Track last modification time for each file (for debouncing re-index)
        self._last_modified_time: Dict[str, float] = {}

    def set_indexed_files(self, file_paths: Set[str]) -> None:
        """
        Set the list of already-indexed file paths.

        Used to determine if a file is new vs modified.
        """
        self._indexed_files = file_paths

    def start(self) -> None:
        """Start watching directories for changes."""
        if self._running:
            logger.warning("Watcher already running")
            return

        self._stop_event.clear()
        self._running = True

        # Start file system observer
        self._observer = Observer()
        handler = ConversationEventHandler(
            self._pending_queue,
            debounce_seconds=self.debounce_seconds
        )

        for watch_dir in self.watched_dirs:
            if watch_dir.exists():
                logger.info(f"Watching directory: {watch_dir}")
                self._observer.schedule(handler, str(watch_dir), recursive=True)

        self._observer.start()

        # Start batch processor thread
        self._processor_thread = threading.Thread(
            target=self._process_pending_updates,
            daemon=True,
            name="ConversationWatcherProcessor"
        )
        self._processor_thread.start()

        logger.info("Conversation watcher started")

    def stop(self) -> None:
        """Stop watching directories."""
        if not self._running:
            return

        self._stop_event.set()
        self._running = False

        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5.0)
            self._observer = None

        if self._processor_thread:
            self._processor_thread.join(timeout=5.0)
            self._processor_thread = None

        logger.info("Conversation watcher stopped")

    def _process_pending_updates(self) -> None:
        """Background thread that batches and processes pending updates."""
        pending_files: Dict[str, str] = {}  # path -> event_type
        last_event_time = 0.0

        while not self._stop_event.is_set():
            try:
                # Get events from queue with timeout
                event_type, file_path = self._pending_queue.get(timeout=1.0)
                pending_files[file_path] = event_type
                last_event_time = time.time()
            except Empty:
                pass

            # Process batch if we have pending files and enough time has passed
            if pending_files and time.time() - last_event_time >= self.batch_delay_seconds:
                self._process_batch(pending_files)
                pending_files.clear()

        # Process any remaining files on shutdown
        if pending_files:
            self._process_batch(pending_files)

    def _process_batch(self, pending_files: Dict[str, str]) -> None:
        """Process a batch of pending file updates."""
        if not pending_files:
            return

        current_time = time.time()
        new_files = []
        modified_files = []

        # Convert debounce minutes to seconds
        modification_debounce_seconds = self.config.indexing.modification_debounce_minutes * 60

        for path, event_type in pending_files.items():
            # New files: not in indexed set, or explicit creation event
            if path not in self._indexed_files or event_type == 'created':
                new_files.append(path)

            # Modified files: already indexed + modification enabled + debounce passed
            elif event_type == 'modified' and self.config.indexing.reindex_on_modification:
                last_modified = self._last_modified_time.get(path, 0)

                # Check if enough time has passed since last modification
                if current_time - last_modified >= modification_debounce_seconds:
                    modified_files.append(path)
                    self._last_modified_time[path] = current_time
                    logger.debug(f"Queuing modified file for re-index: {path}")

        # Process new files
        if new_files:
            logger.info(f"Processing batch of {len(new_files)} new files")
            if self.on_update:
                self.on_update(new_files)
            self._indexed_files.update(new_files)

        # Process modified files
        if modified_files:
            logger.info(f"Re-indexing {len(modified_files)} modified conversations")
            if self.on_update:
                self.on_update(modified_files)

        if not new_files and not modified_files:
            logger.debug("No files to index in batch (some may be debounced)")

    @property
    def is_running(self) -> bool:
        """Check if watcher is currently running."""
        return self._running

    def get_watched_directories(self) -> List[Path]:
        """Get list of directories being watched."""
        return self.watched_dirs.copy()
