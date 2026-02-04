#!/usr/bin/env python3
"""
Unit tests for WhatsApp message deduplication logic.

Tests the thread-safe in-memory cache with TTL that prevents duplicate
message processing on webhook retries.
"""

import pytest
import threading
import time

# Import refactored deduplication module
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from whatsapp.deduplication import MessageDeduplicator


@pytest.fixture
def deduplicator():
    """Create fresh deduplicator instance for each test."""
    return MessageDeduplicator(ttl_seconds=300)


def test_new_message_not_duplicate(deduplicator):
    """Test that a new message ID is not marked as duplicate."""
    msg_id = "wamid.test123"
    assert deduplicator.is_duplicate(msg_id) is False
    # Cache should now contain this message
    assert deduplicator.get_cache_size() == 1


def test_duplicate_message_detected(deduplicator):
    """Test that a duplicate message ID is correctly detected."""
    msg_id = "wamid.test456"

    # First call: not duplicate
    assert deduplicator.is_duplicate(msg_id) is False

    # Second call: duplicate
    assert deduplicator.is_duplicate(msg_id) is True

    # Third call: still duplicate
    assert deduplicator.is_duplicate(msg_id) is True


def test_different_messages_not_duplicate(deduplicator):
    """Test that different message IDs are treated independently."""
    msg_id1 = "wamid.test789"
    msg_id2 = "wamid.test101112"

    assert deduplicator.is_duplicate(msg_id1) is False
    assert deduplicator.is_duplicate(msg_id2) is False

    # Both should now be marked as duplicates
    assert deduplicator.is_duplicate(msg_id1) is True
    assert deduplicator.is_duplicate(msg_id2) is True


def test_ttl_expiration(deduplicator):
    """Test that old entries are cleaned up after TTL expires."""
    msg_id = "wamid.test_ttl"

    # Mark message as processed
    assert deduplicator.is_duplicate(msg_id) is False

    # Manually set timestamp to 6 minutes ago (past TTL of 5 minutes)
    deduplicator._cache[msg_id] = time.time() - 360  # 6 minutes ago

    # Process a different message to trigger cleanup
    new_msg_id = "wamid.trigger_cleanup"
    deduplicator.is_duplicate(new_msg_id)

    # Old entry should be cleaned up
    assert msg_id not in deduplicator._cache
    assert new_msg_id in deduplicator._cache


def test_concurrent_access(deduplicator):
    """Test thread-safe concurrent access to deduplication cache."""
    msg_id = "wamid.concurrent_test"
    results = []

    def check_duplicate():
        """Worker function to check duplicate in thread."""
        is_dup = deduplicator.is_duplicate(msg_id)
        results.append(is_dup)

    # Launch 10 threads simultaneously
    threads = [threading.Thread(target=check_duplicate) for _ in range(10)]

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    # Exactly one thread should get False (new message)
    # All others should get True (duplicate)
    assert results.count(False) == 1
    assert results.count(True) == 9


def test_concurrent_different_messages(deduplicator):
    """Test concurrent processing of different message IDs."""
    msg_ids = [f"wamid.concurrent_{i}" for i in range(20)]
    results = {}

    def check_multiple_messages(msg_id):
        """Worker function to check multiple message IDs."""
        results[msg_id] = deduplicator.is_duplicate(msg_id)

    threads = [threading.Thread(target=check_multiple_messages, args=(mid,))
               for mid in msg_ids]

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    # All messages should be new (not duplicates)
    assert all(is_dup is False for is_dup in results.values())
    assert len(results) == 20


def test_cache_size_bounded(deduplicator):
    """Test that cache doesn't grow unbounded with TTL cleanup."""
    # Add 100 messages
    for i in range(100):
        deduplicator.is_duplicate(f"wamid.bounded_{i}")

    # Cache should have 100 entries
    assert deduplicator.get_cache_size() == 100

    # Set all entries to expired (7 minutes ago)
    old_time = time.time() - 420  # 7 minutes ago
    for msg_id in deduplicator._cache:
        deduplicator._cache[msg_id] = old_time

    # Process a new message to trigger cleanup
    deduplicator.is_duplicate("wamid.trigger_cleanup_bounded")

    # Cache should only have 1 entry now (the new one)
    assert deduplicator.get_cache_size() == 1


def test_edge_case_empty_message_id(deduplicator):
    """Test handling of empty message ID."""
    # Empty string should be treated as a valid ID
    assert deduplicator.is_duplicate("") is False
    assert deduplicator.is_duplicate("") is True


def test_edge_case_very_long_message_id(deduplicator):
    """Test handling of very long message ID."""
    long_id = "wamid." + "x" * 1000
    assert deduplicator.is_duplicate(long_id) is False
    assert deduplicator.is_duplicate(long_id) is True


def test_performance_large_cache(deduplicator):
    """Test performance with large cache (1000 entries)."""
    # Add 1000 messages
    for i in range(1000):
        deduplicator.is_duplicate(f"wamid.perf_{i}")

    # Check duplicate detection is still fast (should be O(1))
    start = time.time()
    deduplicator.is_duplicate("wamid.perf_500")  # Duplicate
    elapsed = time.time() - start

    # Should be very fast (< 10ms even with 1000 entries)
    assert elapsed < 0.01  # 10ms

    # Check new message is also fast
    start = time.time()
    deduplicator.is_duplicate("wamid.perf_new")  # New
    elapsed = time.time() - start

    assert elapsed < 0.01  # 10ms
