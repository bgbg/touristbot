"""
Error message rate limiter.

Prevents flooding users with repeated error messages during backend outages.
Thread-safe in-memory cache with TTL, keyed by phone number.
"""

from __future__ import annotations

import threading
import time
from typing import Dict


class ErrorRateLimiter:
    """
    Thread-safe per-phone error message rate limiter with TTL-based expiration.

    Tracks the last time an error message was sent to each phone number.
    If an error was already sent within the cooldown window, subsequent
    errors are suppressed (returns False) to avoid flooding the user.

    Self-cleaning: Expired entries are automatically removed on each check.
    """

    def __init__(self, cooldown_seconds: int = 120):
        """
        Initialize error rate limiter.

        Args:
            cooldown_seconds: Minimum seconds between error messages per phone (default: 120 = 2 minutes)
        """
        self._cache: Dict[str, float] = {}  # {phone: last_error_timestamp}
        self._lock = threading.Lock()
        self._cooldown_seconds = cooldown_seconds

    def should_send_error(self, phone: str) -> bool:
        """
        Check if an error message should be sent to this phone number.

        Thread-safe check (does NOT record the timestamp). Call
        ``record_error_sent(phone)`` after the message is actually delivered
        so that a failed send does not start the cooldown.

        Also performs cleanup of expired entries.

        Args:
            phone: User phone number

        Returns:
            True if error should be sent, False if suppressed (within cooldown)
        """
        with self._lock:
            now = time.time()
            self._cleanup_expired(now)

            last_sent = self._cache.get(phone)
            if last_sent is not None and (now - last_sent) < self._cooldown_seconds:
                return False  # Suppress — within cooldown

            return True  # Send error

    def record_error_sent(self, phone: str) -> None:
        """
        Record that an error message was successfully sent to this phone.

        Must be called after a successful send so the cooldown starts only
        when the user actually received the message.

        Args:
            phone: User phone number
        """
        with self._lock:
            self._cache[phone] = time.time()

    def _cleanup_expired(self, now: float) -> None:
        """
        Remove expired entries from cache.

        Called automatically during each should_send_error() check.
        Must be called with lock held.

        Args:
            now: Current timestamp (from time.time())
        """
        expired = [
            phone for phone, ts in self._cache.items()
            if now - ts > self._cooldown_seconds
        ]
        for phone in expired:
            del self._cache[phone]

    def get_cache_size(self) -> int:
        """
        Get current cache size (number of entries).

        Thread-safe operation.

        Returns:
            Number of entries in cache
        """
        with self._lock:
            return len(self._cache)

    def clear(self) -> None:
        """
        Clear all entries from cache.

        Thread-safe operation. Useful for testing.
        """
        with self._lock:
            self._cache.clear()
