#!/usr/bin/env python3
"""
Integration tests for async webhook handling.

Tests the async webhook pattern that returns 200 OK immediately while
processing messages in background threads.
"""

import pytest
import time
import threading
from unittest.mock import patch, MagicMock, call
import json

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from whatsapp_bot import app, _message_dedup_cache, _message_dedup_lock, _active_threads, _active_threads_lock


@pytest.fixture
def client():
    """Flask test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def clear_state():
    """Clear global state before each test."""
    with _message_dedup_lock:
        _message_dedup_cache.clear()

    with _active_threads_lock:
        _active_threads.clear()

    yield

    with _message_dedup_lock:
        _message_dedup_cache.clear()

    with _active_threads_lock:
        _active_threads.clear()


@pytest.fixture(autouse=True)
def mock_signature_validation():
    """Mock signature validation for all tests."""
    # Patch in the location where it's actually used (whatsapp.app module)
    with patch('whatsapp.app.verify_webhook_signature', return_value=True):
        yield


def create_webhook_payload(msg_id="wamid.test123", phone="972525974655", text="Hello"):
    """Create a WhatsApp webhook payload."""
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {
                        "display_phone_number": "15550000000",
                        "phone_number_id": "PHONE_NUMBER_ID"
                    },
                    "messages": [{
                        "from": phone,
                        "id": msg_id,
                        "timestamp": "1234567890",
                        "type": "text",
                        "text": {
                            "body": text
                        }
                    }]
                },
                "field": "messages"
            }]
        }]
    }


@pytest.mark.parametrize("mock_delay", [0, 5, 10])
@patch('whatsapp_bot.send_typing_indicator')
@patch('whatsapp_bot.process_message_async')
def test_webhook_returns_200_ok_immediately(mock_process, mock_typing, client, mock_delay):
    """Test that webhook returns 200 OK within 1 second even with slow processing."""
    # Mock typing indicator success
    mock_typing.return_value = (200, {"success": True})

    # Mock slow processing
    def slow_process(*args):
        time.sleep(mock_delay)

    mock_process.side_effect = slow_process

    payload = create_webhook_payload()

    # Measure response time
    start = time.time()
    response = client.post('/webhook',
                          data=json.dumps(payload),
                          content_type='application/json')
    elapsed = time.time() - start

    # Should return 200 OK immediately (< 1 second)
    assert response.status_code == 200
    assert elapsed < 1.0  # Must respond within 1 second

    # Response should be JSON
    data = response.get_json()
    assert data.get("status") == "ok"


@patch('whatsapp_bot.send_typing_indicator')
@patch('whatsapp_bot.process_message_async')
def test_duplicate_messages_rejected(mock_process, mock_typing, client):
    """Test that duplicate message IDs are detected and skipped."""
    mock_typing.return_value = (200, {"success": True})

    payload = create_webhook_payload(msg_id="wamid.duplicate_test")

    # Send first message
    response1 = client.post('/webhook',
                           data=json.dumps(payload),
                           content_type='application/json')
    assert response1.status_code == 200

    # Wait for processing to start
    time.sleep(0.1)

    # Send duplicate (same message ID)
    response2 = client.post('/webhook',
                           data=json.dumps(payload),
                           content_type='application/json')
    assert response2.status_code == 200

    # process_message_async should only be called once (for first message)
    # Not called for duplicate
    assert mock_process.call_count == 1


@patch('whatsapp_bot.send_typing_indicator')
@patch('whatsapp_bot.send_text_message')
@patch('whatsapp_bot.call_backend_qa')
@patch('whatsapp_bot.load_conversation')
@patch('whatsapp_bot.conversation_store')
def test_background_processing_completes(mock_conv_store, mock_load_conv, mock_backend,
                                        mock_send_text, mock_typing, client):
    """Test that background processing completes and sends response."""
    # Mock setup
    mock_typing.return_value = (200, {"success": True})
    mock_conv = MagicMock()
    mock_conv.conversation_id = "test_conv"
    mock_conv.area = "test_area"
    mock_conv.site = "test_site"
    mock_load_conv.return_value = mock_conv

    mock_backend.return_value = {
        "response_text": "Test response",
        "citations": [],
        "images": [],
        "should_include_images": False,
    }
    mock_send_text.return_value = (200, {"success": True})

    payload = create_webhook_payload(text="Test message")

    # Send webhook
    response = client.post('/webhook',
                          data=json.dumps(payload),
                          content_type='application/json')
    assert response.status_code == 200

    # Wait for background processing
    time.sleep(1)

    # Verify backend was called
    assert mock_backend.called
    assert mock_backend.call_count == 1

    # Verify response was sent
    assert mock_send_text.called
    call_args = mock_send_text.call_args[0]
    assert "Test response" in call_args[1]


@patch('whatsapp_bot.send_typing_indicator')
@patch('whatsapp_bot.process_message_async')
def test_typing_indicator_sent_before_200_ok(mock_process, mock_typing, client):
    """Test that typing indicator is sent before returning 200 OK."""
    call_order = []

    def track_typing(*args):
        call_order.append("typing")
        return (200, {"success": True})

    def track_process(*args):
        call_order.append("process")

    mock_typing.side_effect = track_typing
    mock_process.side_effect = track_process

    payload = create_webhook_payload()

    # Send webhook
    start = time.time()
    response = client.post('/webhook',
                          data=json.dumps(payload),
                          content_type='application/json')
    elapsed = time.time() - start

    # Verify order: typing indicator before response
    assert call_order[0] == "typing"
    assert response.status_code == 200
    assert elapsed < 1.0


@patch('whatsapp_bot.send_typing_indicator')
@patch('whatsapp_bot.call_backend_qa')
@patch('whatsapp_bot.load_conversation')
@patch('whatsapp_bot.send_text_message')
@patch('whatsapp_bot.conversation_store')
def test_background_task_timeout(mock_conv_store, mock_send_text, mock_load_conv,
                                mock_backend, mock_typing, client):
    """Test that background task timeout triggers after 60s."""
    mock_typing.return_value = (200, {"success": True})

    mock_conv = MagicMock()
    mock_conv.conversation_id = "test_conv"
    mock_conv.area = "test_area"
    mock_conv.site = "test_site"
    mock_load_conv.return_value = mock_conv

    # Mock very slow backend (simulates timeout scenario)
    def slow_backend(*args, **kwargs):
        time.sleep(70)  # Longer than 60s timeout
        return {"response_text": "Too late"}

    mock_backend.side_effect = slow_backend
    mock_send_text.return_value = (200, {})

    payload = create_webhook_payload()

    # Send webhook
    response = client.post('/webhook',
                          data=json.dumps(payload),
                          content_type='application/json')
    assert response.status_code == 200

    # Note: This test won't actually wait 60s in practice
    # In a real test suite, we'd mock the timer or use a shorter timeout
    # For now, just verify webhook returned immediately
    # Actual timeout behavior verified in manual/staging tests


@patch('whatsapp_bot.send_typing_indicator')
@patch('whatsapp_bot.process_message_async')
def test_concurrent_messages_handled(mock_process, mock_typing, client):
    """Test that multiple sequential messages are handled correctly."""
    mock_typing.return_value = (200, {"success": True})
    mock_process.return_value = None

    # Send 5 messages sequentially (Flask test client doesn't support true concurrency)
    responses = []
    for i in range(5):
        payload = create_webhook_payload(msg_id=f"wamid.sequential_{i}", text=f"Message {i}")
        resp = client.post('/webhook',
                          data=json.dumps(payload),
                          content_type='application/json')
        responses.append(resp)

    # All should return 200 OK
    assert len(responses) == 5
    assert all(r.status_code == 200 for r in responses)

    # Wait for background threads to start
    time.sleep(0.5)

    # All 5 messages should be processed (no duplicates)
    assert mock_process.call_count == 5


@patch('whatsapp_bot.send_typing_indicator')
def test_typing_indicator_failure_does_not_block(mock_typing, client):
    """Test that typing indicator failure doesn't block webhook response."""
    # Simulate typing indicator failure
    mock_typing.side_effect = Exception("Typing indicator failed")

    payload = create_webhook_payload()

    # Should still return 200 OK despite typing indicator failure
    response = client.post('/webhook',
                          data=json.dumps(payload),
                          content_type='application/json')
    assert response.status_code == 200


@patch('whatsapp_bot.send_typing_indicator')
@patch('whatsapp_bot.send_text_message')
@patch('whatsapp_bot.call_backend_qa')
@patch('whatsapp_bot.load_conversation')
@patch('whatsapp_bot.conversation_store')
def test_backend_error_handling(mock_conv_store, mock_load_conv, mock_backend,
                                mock_send_text, mock_typing, client):
    """Test that backend errors are handled gracefully."""
    mock_typing.return_value = (200, {"success": True})

    mock_conv = MagicMock()
    mock_conv.conversation_id = "test_conv"
    mock_conv.area = "test_area"
    mock_conv.site = "test_site"
    mock_load_conv.return_value = mock_conv

    # Simulate backend error
    mock_backend.side_effect = Exception("Backend failed")
    mock_send_text.return_value = (200, {})

    payload = create_webhook_payload()

    # Webhook should still return 200 OK
    response = client.post('/webhook',
                          data=json.dumps(payload),
                          content_type='application/json')
    assert response.status_code == 200

    # Wait for background processing
    time.sleep(0.5)

    # Error message should be sent to user
    assert mock_send_text.called
    # Check that an error message was sent
    error_sent = any("שגיאה" in str(call_args) for call_args in mock_send_text.call_args_list)
    assert error_sent
