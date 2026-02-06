"""
Delivery status tracker for WhatsApp messages.

Tracks outgoing message metadata to correlate with delivery status updates
from WhatsApp webhooks (sent/delivered/read timestamps).
"""

from __future__ import annotations

import time
from typing import Dict, Optional
from threading import Lock


class DeliveryTracker:
    """
    In-memory tracker for correlating outgoing messages with delivery status.

    Stores pending message metadata (correlation_id, sent_timestamp) keyed by
    WhatsApp message_id. When status webhooks arrive, looks up the metadata
    to construct complete timing breakdown.

    Thread-safe with automatic expiration (30-minute TTL).
    """

    def __init__(self, ttl_seconds: int = 1800):
        """
        Initialize delivery tracker.

        Args:
            ttl_seconds: Time-to-live for pending messages (default: 1800s = 30min)
        """
        self.ttl_seconds = ttl_seconds
        self.pending: Dict[str, Dict] = {}  # message_id -> metadata
        self.lock = Lock()
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # Cleanup every 5 minutes

    def register_outgoing_message(
        self,
        message_id: str,
        correlation_id: str,
        phone: str,
        conversation_id: str,
        sent_timestamp_ms: float,
    ) -> None:
        """
        Register an outgoing message for delivery tracking.

        Args:
            message_id: WhatsApp message ID (from API response)
            correlation_id: Request correlation ID
            phone: User phone number
            conversation_id: Conversation ID
            sent_timestamp_ms: Timestamp when message was sent (ms since epoch)
        """
        with self.lock:
            self.pending[message_id] = {
                "correlation_id": correlation_id,
                "phone": phone,
                "conversation_id": conversation_id,
                "sent_timestamp_ms": sent_timestamp_ms,
                "registered_at": time.time(),
            }

    def get(self, message_id: str) -> Optional[Dict]:
        """
        Get metadata for a message without removing it.

        Used to retrieve message metadata for multiple status updates
        (sent/delivered/read) without losing the tracking data.

        Args:
            message_id: WhatsApp message ID

        Returns:
            Metadata dict or None if not found
        """
        with self.lock:
            return self.pending.get(message_id)

    def get_and_remove(self, message_id: str) -> Optional[Dict]:
        """
        Get and remove metadata for a message.

        Used when delivery status arrives - retrieves metadata and cleans up.
        Automatically triggers cleanup of expired entries every 5 minutes.

        Args:
            message_id: WhatsApp message ID

        Returns:
            Metadata dict or None if not found
        """
        # Trigger automatic cleanup periodically (similar to MessageDeduplicator pattern)
        now = time.time()
        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup_expired_internal()
            self._last_cleanup = now

        with self.lock:
            return self.pending.pop(message_id, None)

    def _cleanup_expired_internal(self) -> int:
        """
        Internal method to remove expired entries (older than TTL).
        Called automatically by get_and_remove every 5 minutes.

        Returns:
            Number of entries removed
        """
        now = time.time()
        cutoff = now - self.ttl_seconds

        with self.lock:
            expired = [
                msg_id
                for msg_id, metadata in self.pending.items()
                if metadata["registered_at"] < cutoff
            ]

            for msg_id in expired:
                del self.pending[msg_id]

        return len(expired)

    def cleanup_expired(self) -> int:
        """
        Manually trigger cleanup of expired entries (older than TTL).

        This method can be called explicitly, but cleanup also happens automatically
        every 5 minutes when get_and_remove() is called.

        Returns:
            Number of entries removed
        """
        count = self._cleanup_expired_internal()
        self._last_cleanup = time.time()
        return count

    def get_pending_count(self) -> int:
        """
        Get count of pending messages.

        Returns:
            Number of messages awaiting delivery status
        """
        with self.lock:
            return len(self.pending)
