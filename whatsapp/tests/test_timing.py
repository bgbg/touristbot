"""
Unit tests for timing utilities.

Tests TimingContext for checkpoint tracking, elapsed time calculations,
and timing breakdown generation.
"""

import time
import pytest

from whatsapp.timing import TimingContext


class TestTimingContext:
    """Test suite for TimingContext class."""

    def test_init_with_correlation_id(self):
        """Test TimingContext initialization with correlation ID."""
        ctx = TimingContext(correlation_id="test-123")
        assert ctx.correlation_id == "test-123"
        assert ctx.checkpoints == {}

    def test_init_without_correlation_id(self):
        """Test TimingContext initialization without correlation ID."""
        ctx = TimingContext()
        assert ctx.correlation_id is None
        assert ctx.checkpoints == {}

    def test_mark_creates_checkpoint(self):
        """Test that mark() creates a checkpoint with timestamp."""
        ctx = TimingContext()
        timestamp_ms = ctx.mark("test_checkpoint")

        assert "test_checkpoint" in ctx.checkpoints
        assert isinstance(timestamp_ms, float)
        assert timestamp_ms > 0
        assert ctx.checkpoints["test_checkpoint"] == timestamp_ms

    def test_mark_returns_millisecond_timestamp(self):
        """Test that mark() returns timestamp in milliseconds since epoch."""
        ctx = TimingContext()
        timestamp_ms = ctx.mark("test")

        # Timestamp should be in milliseconds (13 digits for year 2024+)
        assert timestamp_ms > 1_600_000_000_000  # After Sep 2020
        assert timestamp_ms < 2_000_000_000_000  # Before May 2033

    def test_mark_multiple_checkpoints(self):
        """Test marking multiple checkpoints."""
        ctx = TimingContext()

        ts1 = ctx.mark("checkpoint_1")
        time.sleep(0.01)  # Sleep 10ms to ensure different timestamps
        ts2 = ctx.mark("checkpoint_2")
        time.sleep(0.01)
        ts3 = ctx.mark("checkpoint_3")

        assert len(ctx.checkpoints) == 3
        assert ts1 < ts2 < ts3

    def test_get_breakdown_returns_copy(self):
        """Test that get_breakdown() returns a copy of checkpoints."""
        ctx = TimingContext()
        ctx.mark("test")

        breakdown = ctx.get_breakdown()
        breakdown["modified"] = 999

        # Original checkpoints should be unchanged
        assert "modified" not in ctx.checkpoints

    def test_get_breakdown_empty(self):
        """Test get_breakdown() with no checkpoints."""
        ctx = TimingContext()
        breakdown = ctx.get_breakdown()

        assert breakdown == {}
        assert isinstance(breakdown, dict)

    def test_get_elapsed_valid_checkpoints(self):
        """Test get_elapsed() with valid checkpoints."""
        ctx = TimingContext()
        ctx.mark("start")
        time.sleep(0.05)  # Sleep 50ms
        ctx.mark("end")

        elapsed = ctx.get_elapsed("start", "end")

        assert elapsed is not None
        assert elapsed >= 50  # At least 50ms
        assert elapsed < 100  # Should be less than 100ms

    def test_get_elapsed_missing_start_checkpoint(self):
        """Test get_elapsed() with missing start checkpoint."""
        ctx = TimingContext()
        ctx.mark("end")

        elapsed = ctx.get_elapsed("start", "end")
        assert elapsed is None

    def test_get_elapsed_missing_end_checkpoint(self):
        """Test get_elapsed() with missing end checkpoint."""
        ctx = TimingContext()
        ctx.mark("start")

        elapsed = ctx.get_elapsed("start", "end")
        assert elapsed is None

    def test_get_elapsed_both_checkpoints_missing(self):
        """Test get_elapsed() with both checkpoints missing."""
        ctx = TimingContext()

        elapsed = ctx.get_elapsed("start", "end")
        assert elapsed is None

    def test_get_elapsed_zero_duration(self):
        """Test get_elapsed() when checkpoints are set immediately."""
        ctx = TimingContext()
        ctx.mark("start")
        ctx.mark("end")

        elapsed = ctx.get_elapsed("start", "end")

        # Should be very small but non-negative
        assert elapsed is not None
        assert elapsed >= 0
        assert elapsed < 10  # Should be less than 10ms

    def test_get_total_elapsed_with_multiple_checkpoints(self):
        """Test get_total_elapsed() with multiple checkpoints."""
        ctx = TimingContext()
        ctx.mark("first")
        time.sleep(0.05)  # Sleep 50ms
        ctx.mark("middle")
        time.sleep(0.05)  # Sleep 50ms
        ctx.mark("last")

        total = ctx.get_total_elapsed()

        assert total is not None
        assert total >= 100  # At least 100ms
        assert total < 150  # Should be less than 150ms

    def test_get_total_elapsed_with_one_checkpoint(self):
        """Test get_total_elapsed() with only one checkpoint."""
        ctx = TimingContext()
        ctx.mark("only")

        total = ctx.get_total_elapsed()
        assert total is None

    def test_get_total_elapsed_with_no_checkpoints(self):
        """Test get_total_elapsed() with no checkpoints."""
        ctx = TimingContext()

        total = ctx.get_total_elapsed()
        assert total is None

    def test_set_checkpoint_explicit_timestamp(self):
        """Test set_checkpoint() with explicit timestamp value."""
        ctx = TimingContext()
        explicit_ts = 1234567890123.45

        ctx.set_checkpoint("explicit", explicit_ts)

        assert ctx.checkpoints["explicit"] == explicit_ts

    def test_set_checkpoint_overwrites_existing(self):
        """Test that set_checkpoint() can overwrite existing checkpoint."""
        ctx = TimingContext()
        ctx.mark("test")
        original_ts = ctx.checkpoints["test"]

        new_ts = 9999999999999.99
        ctx.set_checkpoint("test", new_ts)

        assert ctx.checkpoints["test"] == new_ts
        assert ctx.checkpoints["test"] != original_ts

    def test_timing_sequence_realistic_scenario(self):
        """Test realistic timing sequence for message processing."""
        ctx = TimingContext(correlation_id="msg-456")

        # Simulate message processing flow
        ctx.mark("webhook_received")
        time.sleep(0.001)
        ctx.mark("background_task_started")
        time.sleep(0.001)
        ctx.mark("message_processing_started")
        time.sleep(0.01)
        ctx.mark("conversation_loaded")
        time.sleep(0.01)
        ctx.mark("backend_request_sent")
        time.sleep(0.02)
        ctx.mark("backend_response_received")
        time.sleep(0.005)
        ctx.mark("text_sent")
        time.sleep(0.005)
        ctx.mark("request_completed")

        # Verify all checkpoints exist
        expected_checkpoints = [
            "webhook_received",
            "background_task_started",
            "message_processing_started",
            "conversation_loaded",
            "backend_request_sent",
            "backend_response_received",
            "text_sent",
            "request_completed"
        ]

        for checkpoint in expected_checkpoints:
            assert checkpoint in ctx.checkpoints

        # Verify elapsed times are reasonable
        total = ctx.get_total_elapsed()
        assert total is not None
        assert total >= 50  # At least 50ms (sum of sleeps)

        # Verify backend processing time
        backend_time = ctx.get_elapsed("backend_request_sent", "backend_response_received")
        assert backend_time is not None
        assert backend_time >= 20  # At least 20ms

    def test_checkpoint_names_are_case_sensitive(self):
        """Test that checkpoint names are case-sensitive."""
        ctx = TimingContext()
        ctx.mark("Test")
        time.sleep(0.001)  # Ensure different timestamps
        ctx.mark("test")

        assert len(ctx.checkpoints) == 2
        assert "Test" in ctx.checkpoints
        assert "test" in ctx.checkpoints
        # Timestamps will be different due to sleep
        assert ctx.checkpoints["Test"] < ctx.checkpoints["test"]

    def test_checkpoint_names_with_special_characters(self):
        """Test checkpoint names with special characters."""
        ctx = TimingContext()

        ctx.mark("checkpoint_with_underscores")
        ctx.mark("checkpoint-with-dashes")
        ctx.mark("checkpoint.with.dots")
        ctx.mark("checkpoint:with:colons")

        assert len(ctx.checkpoints) == 4

    def test_concurrent_context_isolation(self):
        """Test that multiple TimingContext instances are isolated."""
        ctx1 = TimingContext(correlation_id="req-1")
        ctx2 = TimingContext(correlation_id="req-2")

        ctx1.mark("checkpoint_1")
        ctx2.mark("checkpoint_2")

        assert "checkpoint_1" in ctx1.checkpoints
        assert "checkpoint_1" not in ctx2.checkpoints
        assert "checkpoint_2" in ctx2.checkpoints
        assert "checkpoint_2" not in ctx1.checkpoints
