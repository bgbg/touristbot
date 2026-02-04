"""
Background task management with timeout and graceful shutdown.

Provides thread management for async message processing with timeout monitoring
and graceful shutdown coordination.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Any, Set, Optional

from .logging_utils import eprint, EventLogger


class BackgroundTaskManager:
    """
    Background task manager with timeout monitoring and graceful shutdown.

    Manages background threads for async message processing:
    - Tracks active threads
    - Monitors for timeouts (60 seconds default)
    - Coordinates graceful shutdown (waits up to 30 seconds)
    - Periodic monitoring (every 10 messages)
    """

    def __init__(
        self,
        timeout_seconds: int = 60,
        logger: Optional[EventLogger] = None
    ):
        """
        Initialize background task manager.

        Args:
            timeout_seconds: Timeout for background threads in seconds (default: 60)
            logger: Optional event logger for monitoring
        """
        self._active_threads: Set[threading.Thread] = set()
        self._threads_lock = threading.Lock()
        self._timeout_seconds = timeout_seconds
        self._message_counter = 0
        self._counter_lock = threading.Lock()
        self._logger = logger

    def execute_async(
        self,
        target: Callable[..., None],
        *args: Any,
        correlation_id: Optional[str] = None,
        **kwargs: Any
    ) -> threading.Thread:
        """
        Execute function in background thread with timeout monitoring.

        Creates daemon thread that runs target function with timeout wrapper.
        Thread is automatically tracked and removed when complete.

        Args:
            target: Function to execute in background
            *args: Positional arguments for target function
            correlation_id: Optional correlation ID for logging
            **kwargs: Keyword arguments for target function

        Returns:
            Thread object (already started)

        Example:
            manager = BackgroundTaskManager()
            thread = manager.execute_async(
                process_message,
                phone="972501234567",
                text="שלום",
                correlation_id="uuid-123"
            )
            # Thread runs in background, manager monitors for timeout
        """
        # Create timeout wrapper
        thread = None  # Will be set in lambda

        def timeout_wrapper():
            """Wrapper that runs target with timeout monitoring."""
            # Create timeout timer
            timeout_event = threading.Event()

            def timeout_handler():
                """Called when timeout expires."""
                eprint(
                    f"[TIMEOUT] Background task timed out after "
                    f"{self._timeout_seconds}s: {correlation_id}"
                )
                if self._logger:
                    self._logger.log_event("background_task_timeout", {
                        "correlation_id": correlation_id,
                        "timeout_seconds": self._timeout_seconds,
                    }, correlation_id)
                timeout_event.set()

            # Start timeout timer
            timer = threading.Timer(self._timeout_seconds, timeout_handler)
            timer.daemon = True
            timer.start()

            try:
                # Log start
                if self._logger:
                    self._logger.log_event("background_task_started", {
                        "correlation_id": correlation_id,
                    }, correlation_id)

                # Run the actual target function
                # Include correlation_id in kwargs if it was provided
                target_kwargs = kwargs.copy()
                if correlation_id is not None:
                    target_kwargs['correlation_id'] = correlation_id
                target(*args, **target_kwargs)

                # Log completion
                if self._logger:
                    self._logger.log_event("background_task_completed", {
                        "correlation_id": correlation_id,
                    }, correlation_id)

            finally:
                # Cancel timeout timer if completed before timeout
                timer.cancel()

                # Remove from active threads
                with self._threads_lock:
                    if thread:
                        self._active_threads.discard(thread)

        # Create thread
        thread = threading.Thread(target=timeout_wrapper, daemon=True)

        # Track active thread
        with self._threads_lock:
            self._active_threads.add(thread)

        # Start thread
        thread.start()

        # Periodic monitoring (every 10 messages)
        with self._counter_lock:
            self._message_counter += 1
            if self._message_counter % 10 == 0:
                with self._threads_lock:
                    active_count = len(self._active_threads)
                eprint(f"[MONITOR] Processed {self._message_counter} messages, {active_count} active threads")
                if self._logger:
                    self._logger.log_event("periodic_monitor", {
                        "total_messages": self._message_counter,
                        "active_threads": active_count,
                    }, correlation_id)

        return thread

    def get_active_count(self) -> int:
        """
        Get count of active background threads.

        Thread-safe operation.

        Returns:
            Number of active threads
        """
        with self._threads_lock:
            return len(self._active_threads)

    def wait_for_completion(self, max_wait_seconds: int = 30) -> int:
        """
        Wait for all active threads to complete (graceful shutdown).

        Called on SIGTERM/SIGINT signals. Waits up to max_wait_seconds for all
        active threads to complete, then returns.

        Args:
            max_wait_seconds: Maximum time to wait in seconds (default: 30)

        Returns:
            Number of threads still active after wait timeout

        Example:
            manager = BackgroundTaskManager()
            # ... process messages ...
            # On shutdown signal:
            remaining = manager.wait_for_completion(max_wait_seconds=30)
            if remaining > 0:
                print(f"Warning: {remaining} threads still active")
        """
        with self._threads_lock:
            active_count = len(self._active_threads)
            active_threads_snapshot = list(self._active_threads)

        if active_count == 0:
            eprint("✓ No active threads, exiting immediately")
            return 0

        eprint(f"⏳ Waiting for {active_count} active thread(s) to complete (max {max_wait_seconds}s)...")

        # Wait for threads with timeout
        start_time = time.time()
        for thread in active_threads_snapshot:
            remaining_time = max_wait_seconds - (time.time() - start_time)
            if remaining_time <= 0:
                break
            thread.join(timeout=remaining_time)

        with self._threads_lock:
            remaining = len(self._active_threads)

        if remaining == 0:
            eprint(f"✓ All threads completed, exiting")
        else:
            eprint(f"⚠️  {remaining} thread(s) still active after {max_wait_seconds}s, forcing exit")

        return remaining
