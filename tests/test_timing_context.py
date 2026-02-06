"""
Tests for TimingContext class.
"""

import time

from whatsapp.timing import TimingContext


def test_timing_context_basic():
    """Test basic timing context operations."""
    ctx = TimingContext(correlation_id="test-123")

    assert ctx.correlation_id == "test-123"
    assert len(ctx.checkpoints) == 0

    # Mark first checkpoint
    ts1 = ctx.mark("start")
    assert "start" in ctx.checkpoints
    assert ctx.checkpoints["start"] == ts1
    assert ts1 > 0

    # Wait a bit
    time.sleep(0.01)

    # Mark second checkpoint
    ts2 = ctx.mark("end")
    assert "end" in ctx.checkpoints
    assert ts2 > ts1


def test_timing_context_get_breakdown():
    """Test get_breakdown returns copy of checkpoints."""
    ctx = TimingContext()

    ctx.mark("checkpoint1")
    ctx.mark("checkpoint2")

    breakdown = ctx.get_breakdown()

    assert isinstance(breakdown, dict)
    assert "checkpoint1" in breakdown
    assert "checkpoint2" in breakdown

    # Verify it's a copy
    breakdown["new_key"] = 123
    assert "new_key" not in ctx.checkpoints


def test_timing_context_get_elapsed():
    """Test calculating elapsed time between checkpoints."""
    ctx = TimingContext()

    ctx.mark("start")
    time.sleep(0.02)  # Sleep 20ms
    ctx.mark("end")

    elapsed = ctx.get_elapsed("start", "end")

    assert elapsed is not None
    assert elapsed >= 20  # At least 20ms
    assert elapsed < 100  # But not too long


def test_timing_context_get_elapsed_missing():
    """Test get_elapsed returns None for missing checkpoints."""
    ctx = TimingContext()

    ctx.mark("start")

    # Missing end checkpoint
    assert ctx.get_elapsed("start", "end") is None

    # Missing both checkpoints
    assert ctx.get_elapsed("foo", "bar") is None


def test_timing_context_get_total_elapsed():
    """Test calculating total elapsed time."""
    ctx = TimingContext()

    # No checkpoints
    assert ctx.get_total_elapsed() is None

    # Single checkpoint
    ctx.mark("only")
    assert ctx.get_total_elapsed() is None

    # Multiple checkpoints
    ctx.mark("start")
    time.sleep(0.01)
    ctx.mark("middle")
    time.sleep(0.01)
    ctx.mark("end")

    total = ctx.get_total_elapsed()
    assert total is not None
    assert total >= 20  # At least 20ms total


def test_timing_context_marks_in_milliseconds():
    """Test that timestamps are in milliseconds since epoch."""
    ctx = TimingContext()

    before = time.time() * 1000
    ts = ctx.mark("test")
    after = time.time() * 1000

    # Timestamp should be between before and after
    assert before <= ts <= after

    # Should be roughly current time in milliseconds
    # Unix timestamp in milliseconds is 13 digits
    assert len(str(int(ts))) == 13


def test_timing_context_multiple_marks_same_checkpoint():
    """Test marking the same checkpoint multiple times overwrites."""
    ctx = TimingContext()

    ts1 = ctx.mark("test")
    time.sleep(0.01)
    ts2 = ctx.mark("test")

    # Second mark should overwrite first
    assert ctx.checkpoints["test"] == ts2
    assert ts2 > ts1
    assert len(ctx.checkpoints) == 1


def test_timing_context_checkpoint_order_independent():
    """Test that checkpoint order doesn't affect results."""
    ctx = TimingContext()

    # Mark in non-chronological names
    ctx.mark("z_last")
    ctx.mark("a_first")
    ctx.mark("m_middle")

    breakdown = ctx.get_breakdown()
    assert len(breakdown) == 3

    # get_total_elapsed should work regardless of name order
    total = ctx.get_total_elapsed()
    assert total is not None
    assert total >= 0
