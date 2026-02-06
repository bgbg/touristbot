"""
Tests for DeliveryTracker class.
"""

import time

from whatsapp.delivery_tracker import DeliveryTracker


def test_delivery_tracker_register_and_get():
    """Test registering and retrieving messages."""
    tracker = DeliveryTracker(ttl_seconds=60)

    # Register message
    tracker.register_outgoing_message(
        message_id="wamid.123",
        correlation_id="corr-456",
        phone="972501234567",
        conversation_id="whatsapp_972501234567",
        sent_timestamp_ms=1234567890123.45,
    )

    assert tracker.get_pending_count() == 1

    # Retrieve message
    metadata = tracker.get_and_remove("wamid.123")

    assert metadata is not None
    assert metadata["correlation_id"] == "corr-456"
    assert metadata["phone"] == "972501234567"
    assert metadata["conversation_id"] == "whatsapp_972501234567"
    assert metadata["sent_timestamp_ms"] == 1234567890123.45
    assert "registered_at" in metadata

    # Should be removed after retrieval
    assert tracker.get_pending_count() == 0
    assert tracker.get_and_remove("wamid.123") is None


def test_delivery_tracker_get_nonexistent():
    """Test getting non-existent message returns None."""
    tracker = DeliveryTracker()

    result = tracker.get_and_remove("wamid.nonexistent")

    assert result is None


def test_delivery_tracker_multiple_messages():
    """Test tracking multiple messages."""
    tracker = DeliveryTracker()

    # Register multiple messages
    tracker.register_outgoing_message(
        "wamid.1", "corr-1", "phone1", "conv1", 1000.0
    )
    tracker.register_outgoing_message(
        "wamid.2", "corr-2", "phone2", "conv2", 2000.0
    )
    tracker.register_outgoing_message(
        "wamid.3", "corr-3", "phone3", "conv3", 3000.0
    )

    assert tracker.get_pending_count() == 3

    # Retrieve in different order
    meta2 = tracker.get_and_remove("wamid.2")
    assert meta2["correlation_id"] == "corr-2"
    assert tracker.get_pending_count() == 2

    meta1 = tracker.get_and_remove("wamid.1")
    assert meta1["correlation_id"] == "corr-1"
    assert tracker.get_pending_count() == 1

    meta3 = tracker.get_and_remove("wamid.3")
    assert meta3["correlation_id"] == "corr-3"
    assert tracker.get_pending_count() == 0


def test_delivery_tracker_cleanup_expired():
    """Test cleanup of expired entries."""
    tracker = DeliveryTracker(ttl_seconds=1)  # 1-second TTL

    # Register messages
    tracker.register_outgoing_message(
        "wamid.old", "corr-old", "phone", "conv", 1000.0
    )

    assert tracker.get_pending_count() == 1

    # Wait for expiration
    time.sleep(1.2)

    # Register new message
    tracker.register_outgoing_message(
        "wamid.new", "corr-new", "phone", "conv", 2000.0
    )

    assert tracker.get_pending_count() == 2

    # Cleanup expired
    removed_count = tracker.cleanup_expired()

    assert removed_count == 1
    assert tracker.get_pending_count() == 1

    # Old message should be gone
    assert tracker.get_and_remove("wamid.old") is None

    # New message should still be there
    meta = tracker.get_and_remove("wamid.new")
    assert meta is not None


def test_delivery_tracker_cleanup_no_expired():
    """Test cleanup when no entries are expired."""
    tracker = DeliveryTracker(ttl_seconds=60)

    # Register messages
    tracker.register_outgoing_message(
        "wamid.1", "corr-1", "phone", "conv", 1000.0
    )
    tracker.register_outgoing_message(
        "wamid.2", "corr-2", "phone", "conv", 2000.0
    )

    assert tracker.get_pending_count() == 2

    # Cleanup (nothing expired)
    removed_count = tracker.cleanup_expired()

    assert removed_count == 0
    assert tracker.get_pending_count() == 2


def test_delivery_tracker_thread_safety():
    """Test basic thread safety of tracker operations."""
    import threading

    tracker = DeliveryTracker()

    def register_messages(start_id):
        for i in range(10):
            tracker.register_outgoing_message(
                f"wamid.{start_id}_{i}",
                f"corr-{start_id}_{i}",
                "phone",
                "conv",
                float(i),
            )

    # Run registration in parallel threads
    thread1 = threading.Thread(target=register_messages, args=(1,))
    thread2 = threading.Thread(target=register_messages, args=(2,))

    thread1.start()
    thread2.start()

    thread1.join()
    thread2.join()

    # Should have 20 messages total
    assert tracker.get_pending_count() == 20


def test_delivery_tracker_overwrite_same_message_id():
    """Test that registering same message_id twice overwrites."""
    tracker = DeliveryTracker()

    # Register first time
    tracker.register_outgoing_message(
        "wamid.123", "corr-1", "phone1", "conv1", 1000.0
    )

    # Register again with different data
    tracker.register_outgoing_message(
        "wamid.123", "corr-2", "phone2", "conv2", 2000.0
    )

    # Should only have 1 entry
    assert tracker.get_pending_count() == 1

    # Should have latest data
    meta = tracker.get_and_remove("wamid.123")
    assert meta["correlation_id"] == "corr-2"
    assert meta["phone"] == "phone2"
    assert meta["sent_timestamp_ms"] == 2000.0
