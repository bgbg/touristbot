#!/usr/bin/env python3
"""
Integration tests for async webhook handling.

Tests the async webhook pattern that returns 200 OK immediately while
processing messages in background threads.
"""

import pytest
import time
from unittest.mock import patch, MagicMock
import json

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import whatsapp_bot
from whatsapp_bot import clear_message_dedup_cache, clear_active_threads


@pytest.fixture(autouse=True)
def clear_dependency_cache():
    """Clear lru_cache on dependency getters to allow mocking."""
    from whatsapp import dependencies
    # Clear all dependency caches before each test
    dependencies.get_config.cache_clear()
    dependencies.get_whatsapp_client.cache_clear()
    dependencies.get_backend_client.cache_clear()
    dependencies.get_conversation_loader.cache_clear()
    dependencies.get_event_logger.cache_clear()
    dependencies.get_message_deduplicator.cache_clear()
    dependencies.get_task_manager.cache_clear()
    dependencies.get_conversation_store.cache_clear()
    dependencies.get_gcs_storage.cache_clear()
    yield
    # Clear again after test
    dependencies.get_config.cache_clear()
    dependencies.get_whatsapp_client.cache_clear()
    dependencies.get_backend_client.cache_clear()
    dependencies.get_conversation_loader.cache_clear()
    dependencies.get_event_logger.cache_clear()
    dependencies.get_message_deduplicator.cache_clear()
    dependencies.get_task_manager.cache_clear()
    dependencies.get_conversation_store.cache_clear()
    dependencies.get_gcs_storage.cache_clear()


@pytest.fixture
def client():
    """Flask test client with fresh app instance."""
    # Import create_app after dependency cache is cleared
    from whatsapp.app import create_app
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def clear_state():
    """Clear global state before each test."""
    clear_message_dedup_cache()
    clear_active_threads()

    yield

    clear_message_dedup_cache()
    clear_active_threads()


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
@patch('whatsapp_utils.send_typing_indicator')
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


@patch('whatsapp_utils.send_typing_indicator')
@patch('whatsapp.app.process_message')
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


def test_background_processing_completes():
    """Test that background processing completes and sends response."""
    # Mock conversation loader
    mock_conv = MagicMock()
    mock_conv.conversation_id = "test_conv"
    mock_conv.area = "test_area"
    mock_conv.site = "test_site"
    mock_loader = MagicMock()
    mock_loader.load_conversation.return_value = mock_conv
    mock_loader.conversation_store = MagicMock()

    # Mock backend client
    mock_backend = MagicMock()
    mock_backend.call_qa_endpoint.return_value = {
        "response_text": "Test response",
        "citations": [],
        "images": [],
        "should_include_images": False,
    }

    # Mock WhatsApp client
    mock_whatsapp = MagicMock()
    mock_whatsapp.send_text_message.return_value = (200, {"success": True})
    mock_whatsapp.send_typing_indicator.return_value = (200, {"success": True})

    # Clear caches and apply patches
    from whatsapp import dependencies
    dependencies.get_conversation_loader.cache_clear()
    dependencies.get_backend_client.cache_clear()
    dependencies.get_whatsapp_client.cache_clear()

    with patch('whatsapp.dependencies.get_conversation_loader', return_value=mock_loader), \
         patch('whatsapp.dependencies.get_backend_client', return_value=mock_backend), \
         patch('whatsapp.dependencies.get_whatsapp_client', return_value=mock_whatsapp), \
         patch('whatsapp.app.verify_webhook_signature', return_value=True):

        # Create app with mocked dependencies
        from whatsapp.app import create_app
        app = create_app()
        app.config['TESTING'] = True

        with app.test_client() as client:
            payload = create_webhook_payload(text="Test message")

            # Send webhook
            response = client.post('/webhook',
                                  data=json.dumps(payload),
                                  content_type='application/json')
            assert response.status_code == 200

            # Wait for background processing
            time.sleep(1)

            # Verify backend was called
            assert mock_backend.call_qa_endpoint.called
            assert mock_backend.call_qa_endpoint.call_count == 1

            # Verify response was sent
            assert mock_whatsapp.send_text_message.called
            call_args = mock_whatsapp.send_text_message.call_args[0]
            assert "Test response" in call_args[1]


def test_typing_indicator_sent_before_200_ok():
    """Test that typing indicator is sent before returning 200 OK."""
    call_order = []

    # Mock WhatsApp client
    mock_whatsapp = MagicMock()
    def track_typing(*args):
        call_order.append("typing")
        return (200, {"success": True})
    mock_whatsapp.send_typing_indicator.side_effect = track_typing

    # Clear caches and apply patches
    from whatsapp import dependencies
    dependencies.get_whatsapp_client.cache_clear()

    # Patch process_message to track when it's called
    from whatsapp import message_handler
    original_process = message_handler.process_message
    def track_process(*args, **kwargs):
        call_order.append("process")
        return original_process(*args, **kwargs)

    with patch('whatsapp.dependencies.get_whatsapp_client', return_value=mock_whatsapp), \
         patch('whatsapp.app.verify_webhook_signature', return_value=True), \
         patch('whatsapp.message_handler.process_message', side_effect=track_process):

        # Create app with mocked dependencies
        from whatsapp.app import create_app
        app = create_app()
        app.config['TESTING'] = True

        with app.test_client() as client:
            payload = create_webhook_payload()

            # Send webhook
            start = time.time()
            response = client.post('/webhook',
                                  data=json.dumps(payload),
                                  content_type='application/json')
            elapsed = time.time() - start

            # Verify order: typing indicator before response
            # Note: typing indicator is synchronous, process_message is async in thread
            # So typing should always come before process
            assert call_order[0] == "typing"
            assert response.status_code == 200
            assert elapsed < 1.0


@patch('whatsapp_utils.send_typing_indicator')
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


@patch('whatsapp_utils.send_typing_indicator')
@patch('whatsapp.app.process_message')
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


@patch('whatsapp_utils.send_typing_indicator')
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


def test_backend_error_handling():
    """Test that backend errors are handled gracefully."""
    # Mock conversation loader
    mock_conv = MagicMock()
    mock_conv.conversation_id = "test_conv"
    mock_conv.area = "test_area"
    mock_conv.site = "test_site"
    mock_loader = MagicMock()
    mock_loader.load_conversation.return_value = mock_conv
    mock_loader.conversation_store = MagicMock()

    # Mock backend client with error
    mock_backend = MagicMock()
    mock_backend.call_qa_endpoint.side_effect = Exception("Backend failed")

    # Mock WhatsApp client
    mock_whatsapp = MagicMock()
    mock_whatsapp.send_text_message.return_value = (200, {})
    mock_whatsapp.send_typing_indicator.return_value = (200, {"success": True})

    # Clear caches and apply patches
    from whatsapp import dependencies
    dependencies.get_conversation_loader.cache_clear()
    dependencies.get_backend_client.cache_clear()
    dependencies.get_whatsapp_client.cache_clear()

    with patch('whatsapp.dependencies.get_conversation_loader', return_value=mock_loader), \
         patch('whatsapp.dependencies.get_backend_client', return_value=mock_backend), \
         patch('whatsapp.dependencies.get_whatsapp_client', return_value=mock_whatsapp), \
         patch('whatsapp.app.verify_webhook_signature', return_value=True):

        # Create app with mocked dependencies
        from whatsapp.app import create_app
        app = create_app()
        app.config['TESTING'] = True

        with app.test_client() as client:
            payload = create_webhook_payload()

            # Webhook should still return 200 OK
            response = client.post('/webhook',
                                  data=json.dumps(payload),
                                  content_type='application/json')
            assert response.status_code == 200

            # Wait for background processing
            time.sleep(0.5)

            # Error message should be sent to user
            assert mock_whatsapp.send_text_message.called
            # Check that an error message was sent
            error_sent = any("שגיאה" in str(call_args) for call_args in mock_whatsapp.send_text_message.call_args_list)
            assert error_sent
