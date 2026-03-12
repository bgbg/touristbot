#!/usr/bin/env python3
"""
Unit tests for WhatsApp error message rate limiter.

Tests the thread-safe per-phone cooldown cache that prevents flooding
users with repeated error messages during backend outages.
"""

import pytest
import threading
import time

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from whatsapp.error_rate_limiter import ErrorRateLimiter


@pytest.fixture
def limiter():
    """Create fresh rate limiter instance for each test."""
    return ErrorRateLimiter(cooldown_seconds=120)


def test_first_error_allowed(limiter):
    """First error for a phone should be sent."""
    assert limiter.should_send_error("972501234567") is True
    assert limiter.get_cache_size() == 1


def test_second_error_within_cooldown_suppressed(limiter):
    """Second error within cooldown window should be suppressed."""
    phone = "972501234567"
    assert limiter.should_send_error(phone) is True
    assert limiter.should_send_error(phone) is False
    assert limiter.should_send_error(phone) is False


def test_error_after_cooldown_allowed(limiter):
    """Error after cooldown expires should be sent again."""
    phone = "972501234567"
    assert limiter.should_send_error(phone) is True

    # Manually set timestamp to past cooldown
    limiter._cache[phone] = time.time() - 200  # 200s ago, cooldown is 120s

    assert limiter.should_send_error(phone) is True


def test_different_phones_independent(limiter):
    """Each phone number has its own independent cooldown."""
    phone1 = "972501111111"
    phone2 = "972502222222"

    assert limiter.should_send_error(phone1) is True
    assert limiter.should_send_error(phone2) is True

    # Both should now be suppressed
    assert limiter.should_send_error(phone1) is False
    assert limiter.should_send_error(phone2) is False


def test_concurrent_access(limiter):
    """Thread-safe concurrent access should allow exactly one error per phone."""
    phone = "972501234567"
    results = []

    def check():
        results.append(limiter.should_send_error(phone))

    threads = [threading.Thread(target=check) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count(True) == 1
    assert results.count(False) == 9


def test_ttl_cleanup(limiter):
    """Expired entries should be cleaned up automatically."""
    # Add entries
    for i in range(10):
        limiter.should_send_error(f"97250{i:07d}")

    assert limiter.get_cache_size() == 10

    # Expire all entries
    old_time = time.time() - 300
    for phone in limiter._cache:
        limiter._cache[phone] = old_time

    # Trigger cleanup via new check
    limiter.should_send_error("972509999999")

    # Only the new entry should remain
    assert limiter.get_cache_size() == 1


def test_clear(limiter):
    """Clear should remove all entries."""
    limiter.should_send_error("972501234567")
    limiter.should_send_error("972507654321")
    assert limiter.get_cache_size() == 2

    limiter.clear()
    assert limiter.get_cache_size() == 0

    # After clear, errors should be allowed again
    assert limiter.should_send_error("972501234567") is True


def test_custom_cooldown():
    """Custom cooldown seconds should be respected."""
    limiter = ErrorRateLimiter(cooldown_seconds=5)
    phone = "972501234567"

    assert limiter.should_send_error(phone) is True

    # Set timestamp to 6 seconds ago (past 5s cooldown)
    limiter._cache[phone] = time.time() - 6

    assert limiter.should_send_error(phone) is True
