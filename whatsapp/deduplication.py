"""
Message deduplication cache.

Prevents duplicate processing of messages on webhook retries using thread-safe
in-memory cache with TTL (5 minutes default).
"""

from __future__ import annotations

import threading
import time
from typing import Dict


class MessageDeduplicator:
    """
    Thread-safe message deduplication cache with TTL-based expiration.

    Uses in-memory cache to track recently processed message IDs. Webhook retries
    from Meta will deliver the same message ID multiple times, so we need to
    deduplicate to avoid processing the same message twice.

    Self-cleaning: Expired entries are automatically removed on each check.
    """

    def __init__(self, ttl_seconds: int = 300):
        """
        Initialize deduplication cache.

        Args:
            ttl_seconds: Time-to-live for cache entries in seconds (default: 300 = 5 minutes)
        """
        self._cache: Dict[str, float] = {}  # {message_id: timestamp}
        self._lock = threading.Lock()
        self._ttl_seconds = ttl_seconds

    def is_duplicate(self, message_id: str) -> bool:
        """
        Check if message ID has been processed recently (within TTL window).

        Thread-safe atomic check-and-set operation. If message is new, marks it as
        processed and returns False. If message was recently processed (within TTL),
        returns True.

        Also performs cleanup of expired entries (TTL expiration).

        Args:
            message_id: WhatsApp message ID from webhook

        Returns:
            True if message is duplicate (already processed), False if new

        Example:
            deduplicator = MessageDeduplicator()
            if deduplicator.is_duplicate(msg_id):
                print("Duplicate message, skipping")
                return
            # Process message...
        """
        with self._lock:
            now = time.time()

            # Cleanup expired entries (TTL expiration)
            self._cleanup_expired(now)

            # Check if message already processed
            if message_id in self._cache:
                return True  # Duplicate

            # Mark as processed
            self._cache[message_id] = now
            return False  # New message

    def _cleanup_expired(self, now: float) -> None:
        """
        Remove expired entries from cache.

        Called automatically during each is_duplicate() check.
        Must be called with lock held.

        Args:
            now: Current timestamp (from time.time())
        """
        expired_ids = [
            mid for mid, ts in self._cache.items()
            if now - ts > self._ttl_seconds
        ]
        for mid in expired_ids:
            del self._cache[mid]

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
