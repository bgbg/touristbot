"""
Timing utilities for measuring WhatsApp bot message pipeline performance.

Provides TimingContext for tracking timing checkpoints throughout message processing.
"""

from __future__ import annotations

import time
from typing import Dict, Optional


class TimingContext:
    """
    Request-scoped timing context for tracking checkpoints.

    Tracks timing checkpoints throughout the message processing pipeline from
    webhook arrival to message delivery. All timestamps in milliseconds since epoch.

    Example:
        ctx = TimingContext(correlation_id="uuid-123")
        ctx.mark("webhook_received")
        # ... do work ...
        ctx.mark("conversation_loaded")
        breakdown = ctx.get_breakdown()
        # {"webhook_received": 1234567890123, "conversation_loaded": 1234567890500}
    """

    def __init__(self, correlation_id: Optional[str] = None):
        """
        Initialize timing context.

        Args:
            correlation_id: Optional correlation ID for cross-referencing with logs
        """
        self.correlation_id = correlation_id
        self.checkpoints: Dict[str, float] = {}

    def mark(self, checkpoint_name: str) -> float:
        """
        Mark a timing checkpoint with current timestamp.

        Args:
            checkpoint_name: Name of the checkpoint (e.g., "webhook_received")

        Returns:
            Timestamp in milliseconds since epoch

        Example:
            timestamp_ms = ctx.mark("backend_request_sent")
        """
        timestamp_ms = time.time() * 1000
        self.checkpoints[checkpoint_name] = timestamp_ms
        return timestamp_ms

    def get_breakdown(self) -> Dict[str, float]:
        """
        Get timing breakdown as dict of checkpoint names to timestamps.

        Returns:
            Dict mapping checkpoint names to timestamps (milliseconds since epoch)

        Example:
            breakdown = ctx.get_breakdown()
            # {
            #   "webhook_received": 1234567890123,
            #   "conversation_loaded": 1234567890500,
            #   "backend_request_sent": 1234567891000
            # }
        """
        return self.checkpoints.copy()

    def get_elapsed(self, start_checkpoint: str, end_checkpoint: str) -> Optional[float]:
        """
        Calculate elapsed time between two checkpoints.

        Args:
            start_checkpoint: Starting checkpoint name
            end_checkpoint: Ending checkpoint name

        Returns:
            Elapsed time in milliseconds, or None if checkpoints don't exist

        Example:
            elapsed_ms = ctx.get_elapsed("webhook_received", "conversation_loaded")
            # 377.0 (ms)
        """
        if start_checkpoint not in self.checkpoints or end_checkpoint not in self.checkpoints:
            return None

        return self.checkpoints[end_checkpoint] - self.checkpoints[start_checkpoint]

    def get_total_elapsed(self) -> Optional[float]:
        """
        Calculate total elapsed time from first to last checkpoint.

        Returns:
            Total elapsed time in milliseconds, or None if less than 2 checkpoints

        Example:
            total_ms = ctx.get_total_elapsed()
            # 5432.1 (ms from first to last checkpoint)
        """
        if len(self.checkpoints) < 2:
            return None

        timestamps = list(self.checkpoints.values())
        return max(timestamps) - min(timestamps)

    def set_checkpoint(self, checkpoint_name: str, timestamp_ms: float) -> None:
        """
        Set a checkpoint with an explicit timestamp value.

        Used for copying checkpoints between contexts or setting initial values.

        Args:
            checkpoint_name: Name of the checkpoint
            timestamp_ms: Timestamp in milliseconds since epoch

        Example:
            ctx.set_checkpoint("webhook_received", 1234567890123.45)
        """
        self.checkpoints[checkpoint_name] = timestamp_ms
