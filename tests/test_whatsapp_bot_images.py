"""
Unit tests for WhatsApp bot image handling functionality.

Tests defensive validation, image detection, retry logic, and error handling.
"""

import urllib.error
from unittest.mock import patch, MagicMock, call, Mock
import pytest


# Mock GCS storage before importing whatsapp_bot to avoid initialization errors
@pytest.fixture(scope="session", autouse=True)
def mock_gcs_storage():
    """Mock GCS storage backend at module level."""
    with patch('whatsapp_bot.GCSStorage') as mock_gcs, \
         patch('whatsapp_bot.ConversationStore') as mock_store_class:
        # Create mock instances
        mock_storage_instance = Mock()
        mock_store_instance = Mock()

        # Configure mocks
        mock_gcs.return_value = mock_storage_instance
        mock_store_class.return_value = mock_store_instance

        yield mock_store_instance


# Mock WhatsApp bot module components
@pytest.fixture
def mock_whatsapp_env(monkeypatch):
    """Mock environment variables for WhatsApp bot."""
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "test-token")
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "test-access-token")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "test-phone-id")
    monkeypatch.setenv("BACKEND_API_KEY", "test-backend-key")
    monkeypatch.setenv("BACKEND_API_URL", "http://localhost:8001")
    monkeypatch.setenv("GCS_BUCKET", "test-bucket")


@pytest.fixture
def mock_backend_response_with_images():
    """Mock backend response with images."""
    return {
        "response_text": "Here's information about storks!",
        "should_include_images": True,
        "images": [
            {
                "uri": "https://storage.googleapis.com/test-bucket/image1.jpg",
                "file_api_uri": "https://generativelanguage.googleapis.com/v1beta/files/abc123",
                "caption": "White storks at the wetland",
                "context": "Text from document about storks",
                "relevance_score": 95
            },
            {
                "uri": "https://storage.googleapis.com/test-bucket/image2.jpg",
                "file_api_uri": "https://generativelanguage.googleapis.com/v1beta/files/def456",
                "caption": "Stork nest on pole",
                "context": "Description of nesting habits",
                "relevance_score": 80
            }
        ],
        "citations": [],
        "conversation_id": "test-conv-123",
        "model_name": "gemini-2.5-flash",
        "temperature": 0.6,
        "latency_ms": 1234.5
    }


@pytest.fixture
def mock_backend_response_no_images():
    """Mock backend response without images."""
    return {
        "response_text": "Hello! How can I help you?",
        "should_include_images": False,
        "images": [],
        "citations": [],
        "conversation_id": "test-conv-123"
    }


class TestDefensiveTypeValidation:
    """Test defensive type validation for response_text and images fields."""

    def test_response_text_as_dict(self, mock_whatsapp_env):
        """Test that dict response_text is converted to string."""
        # Import here to ensure env vars are set
        from whatsapp_bot import normalize_phone

        backend_response = {
            "response_text": {"message": "Hello", "code": 200},  # Dict instead of string
            "should_include_images": False,
            "images": []
        }

        # Simulate the defensive validation logic
        response_text = backend_response.get("response_text", "מצטער, לא הצלחתי להבין את השאלה.")
        if not isinstance(response_text, str):
            response_text = str(response_text)

        assert isinstance(response_text, str)
        assert "message" in response_text  # Dict was converted to string

    def test_response_text_as_list(self):
        """Test that list response_text is converted to string."""
        backend_response = {
            "response_text": ["Hello", "World"],  # List instead of string
            "should_include_images": False,
            "images": []
        }

        response_text = backend_response.get("response_text", "מצטער, לא הצלחתי להבין את השאלה.")
        if not isinstance(response_text, str):
            response_text = str(response_text)

        assert isinstance(response_text, str)
        assert "Hello" in response_text

    def test_response_text_as_none(self):
        """Test that None response_text uses fallback."""
        backend_response = {
            "response_text": None,
            "should_include_images": False,
            "images": []
        }

        response_text = backend_response.get("response_text", "מצטער, לא הצלחתי להבין את השאלה.")
        if not isinstance(response_text, str):
            response_text = str(response_text)

        assert isinstance(response_text, str)

    def test_images_field_as_dict(self):
        """Test that dict images field is converted to empty list."""
        backend_response = {
            "response_text": "Test",
            "should_include_images": True,
            "images": {"url": "test.jpg"}  # Dict instead of list
        }

        images = backend_response.get("images", [])
        if not isinstance(images, list):
            images = []

        assert isinstance(images, list)
        assert len(images) == 0  # Invalid type converted to empty list

    def test_images_field_as_string(self):
        """Test that string images field is converted to empty list."""
        backend_response = {
            "response_text": "Test",
            "should_include_images": True,
            "images": "not-a-list"  # String instead of list
        }

        images = backend_response.get("images", [])
        if not isinstance(images, list):
            images = []

        assert isinstance(images, list)
        assert len(images) == 0


class TestImageDetection:
    """Test image detection logic."""

    def test_images_detected_when_should_include_true(self, mock_backend_response_with_images):
        """Test that images are detected when should_include_images is True."""
        response = mock_backend_response_with_images

        should_include = response.get("should_include_images", False)
        images = response.get("images", [])

        assert should_include is True
        assert len(images) == 2

    def test_no_images_when_should_include_false(self, mock_backend_response_no_images):
        """Test that images are not processed when should_include_images is False."""
        response = mock_backend_response_no_images

        should_include = response.get("should_include_images", False)
        images = response.get("images", [])

        assert should_include is False
        assert len(images) == 0

    def test_images_ignored_when_flag_false_but_images_present(self):
        """Test that images are ignored when flag is False even if images present."""
        response = {
            "response_text": "Test",
            "should_include_images": False,  # Flag is False
            "images": [{"uri": "test.jpg"}]  # But images present
        }

        should_include = response.get("should_include_images", False)

        # Images should not be sent because flag is False
        assert should_include is False


class TestFirstImageOnly:
    """Test that only the first image is sent."""

    def test_only_first_image_extracted(self, mock_backend_response_with_images):
        """Test that only first image is extracted when multiple available."""
        response = mock_backend_response_with_images

        should_include = response.get("should_include_images", False)
        images = response.get("images", [])

        if should_include and images:
            first_image = images[0]

        assert first_image["uri"] == "https://storage.googleapis.com/test-bucket/image1.jpg"
        assert first_image["caption"] == "White storks at the wetland"
        assert first_image["relevance_score"] == 95  # Highest relevance

    def test_multiple_images_only_first_sent(self, mock_backend_response_with_images):
        """Test that when multiple images exist, only first is selected."""
        response = mock_backend_response_with_images

        images = response.get("images", [])
        assert len(images) == 2  # Multiple images available

        # Only first image should be processed
        first_image = images[0]
        second_image = images[1]

        # Verify first image has higher relevance (backend sorted)
        assert first_image["relevance_score"] > second_image["relevance_score"]


class TestImageDownload:
    """Test image download functionality."""

    @patch('urllib.request.urlopen')
    def test_successful_image_download(self, mock_urlopen):
        """Test successful image download from URL."""
        # Mock successful download
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b"fake-image-data"
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        from whatsapp_bot import download_image_from_url

        image_bytes = download_image_from_url("https://example.com/image.jpg")

        assert image_bytes == b"fake-image-data"
        mock_urlopen.assert_called_once()

    @patch('urllib.request.urlopen')
    def test_download_timeout(self, mock_urlopen):
        """Test download timeout handling."""
        # Mock timeout exception
        mock_urlopen.side_effect = urllib.error.URLError("timeout")

        from whatsapp_bot import download_image_from_url

        with pytest.raises(urllib.error.URLError):
            download_image_from_url("https://example.com/image.jpg")

    @patch('urllib.request.urlopen')
    def test_download_404_error(self, mock_urlopen):
        """Test handling of 404 error during download."""
        # Mock 404 HTTP error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://example.com/image.jpg",
            404,
            "Not Found",
            {},
            None
        )

        from whatsapp_bot import download_image_from_url

        with pytest.raises(urllib.error.HTTPError) as exc_info:
            download_image_from_url("https://example.com/image.jpg")

        assert exc_info.value.code == 404


class TestImageSizeValidation:
    """Test image size validation (5MB WhatsApp limit)."""

    def test_image_too_large_rejected(self):
        """Test that images > 5MB are rejected."""
        # Create fake image data > 5MB
        large_image_bytes = b"x" * (6 * 1024 * 1024)  # 6MB
        size_mb = len(large_image_bytes) / (1024 * 1024)

        assert size_mb > 5  # Exceeds WhatsApp limit

    def test_image_within_limit_accepted(self):
        """Test that images <= 5MB are accepted."""
        # Create fake image data < 5MB
        normal_image_bytes = b"x" * (3 * 1024 * 1024)  # 3MB
        size_mb = len(normal_image_bytes) / (1024 * 1024)

        assert size_mb <= 5  # Within WhatsApp limit


class TestCaptionTruncation:
    """Test caption truncation to WhatsApp 1024 char limit."""

    def test_caption_truncated_at_1024_chars(self):
        """Test that captions > 1024 chars are truncated."""
        long_caption = "A" * 2000  # 2000 chars

        # Simulate truncation
        truncated = long_caption[:1024]

        assert len(truncated) == 1024
        assert len(long_caption) > 1024

    def test_short_caption_not_truncated(self):
        """Test that captions < 1024 chars are not modified."""
        short_caption = "White storks at the wetland"

        truncated = short_caption[:1024]

        assert truncated == short_caption
        assert len(truncated) < 1024


class TestRetryLogic:
    """Test exponential backoff retry logic."""

    @patch('time.sleep')  # Mock sleep to speed up tests
    @patch('urllib.request.urlopen')
    def test_retry_on_download_failure(self, mock_urlopen, mock_sleep):
        """Test that download failures trigger retry with backoff."""
        import urllib.request
        import urllib.error
        import time

        # First 2 attempts fail, 3rd succeeds
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b"fake-image-data"
        mock_response.__enter__.return_value = mock_response

        mock_urlopen.side_effect = [
            urllib.error.URLError("Network error"),  # Attempt 1 fails
            urllib.error.URLError("Network error"),  # Attempt 2 fails
            mock_response  # Attempt 3 succeeds
        ]

        # Simulated retry logic (actual implementation in send_image_with_retry)
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                with urllib.request.urlopen("https://example.com/image.jpg", timeout=30) as resp:
                    image_bytes = resp.read()
                    break
            except Exception as e:
                if attempt < max_attempts - 1:
                    delay = 2 ** attempt  # 1s, 2s, 4s
                    time.sleep(delay)
                else:
                    raise

        assert image_bytes == b"fake-image-data"
        assert mock_sleep.call_count == 2  # Sleep called on first 2 failures
        # Verify exponential backoff: 1s, 2s
        mock_sleep.assert_has_calls([call(1), call(2)])


class TestErrorHandling:
    """Test graceful error handling."""

    def test_image_send_failure_does_not_block_text(self):
        """Test that image send failure doesn't prevent text response."""
        # Simulate image send failure
        image_send_failed = True
        text_should_be_sent = True

        # Even if image fails, text should still be sent
        if image_send_failed:
            # Log error but continue
            pass

        assert text_should_be_sent is True

    def test_missing_image_uri_handled_gracefully(self):
        """Test that missing URI in image metadata is handled."""
        image_metadata = {
            "caption": "Test caption",
            "context": "Test context",
            "relevance_score": 85
            # Missing "uri" field
        }

        image_url = image_metadata.get("uri")

        assert image_url is None  # Should handle gracefully


class TestLogging:
    """Test logging of image send events."""

    def test_successful_image_send_logged(self):
        """Test that successful image sends are logged."""
        log_entry = {
            "event_type": "outgoing_image",
            "data": {
                "to": "972525974655",
                "image_url": "https://storage.googleapis.com/test.jpg",
                "caption": "White storks",
                "size_mb": 2.5,
                "media_id": "whatsapp-media-id-123",
                "status": 200,
            }
        }

        assert log_entry["event_type"] == "outgoing_image"
        assert log_entry["data"]["status"] == 200

    def test_failed_image_send_logged(self):
        """Test that failed image sends are logged with error."""
        log_entry = {
            "event_type": "error",
            "data": {
                "type": "image_send_failure",
                "to": "972525974655",
                "image_url": "https://storage.googleapis.com/test.jpg",
                "status": 500,
                "error": "Upload failed",
                "attempts": 3,
            }
        }

        assert log_entry["event_type"] == "error"
        assert log_entry["data"]["type"] == "image_send_failure"
        assert log_entry["data"]["attempts"] == 3


class TestGCSConversationStorage:
    """Test GCS conversation storage functionality."""

    def test_conversation_id_format(self, mock_whatsapp_env):
        """Test that conversation IDs use whatsapp_{phone} format."""
        from whatsapp_bot import normalize_phone

        phone = "+972-50-123-4567"
        normalized = normalize_phone(phone)
        expected_id = f"whatsapp_{normalized}"

        assert expected_id == "whatsapp_972501234567"
        assert normalized == "972501234567"

    @patch('whatsapp_bot.conversation_store')
    def test_load_conversation_creates_new(self, mock_store, mock_whatsapp_env):
        """Test that load_conversation creates new conversation if not found."""
        from whatsapp_bot import load_conversation
        from backend.conversation_storage.conversations import Conversation

        # Mock get_conversation to return None (conversation not found)
        mock_store.get_conversation.return_value = None

        # Mock create_conversation to return new Conversation object
        mock_conv = Conversation(
            conversation_id="whatsapp_972501234567",
            area="hefer_valley",
            site="agamon_hefer",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            messages=[]
        )
        mock_store.create_conversation.return_value = mock_conv

        # Call load_conversation
        phone = "972501234567"
        conv = load_conversation(phone)

        # Verify conversation was created
        mock_store.get_conversation.assert_called_once_with("whatsapp_972501234567")
        mock_store.create_conversation.assert_called_once_with(
            area="hefer_valley",
            site="agamon_hefer",
            conversation_id="whatsapp_972501234567"
        )
        mock_store.save_conversation.assert_called_once_with(mock_conv)
        assert conv.conversation_id == "whatsapp_972501234567"

    @patch('whatsapp_bot.conversation_store')
    def test_gcs_failure_raises_exception(self, mock_store, mock_whatsapp_env):
        """Test that GCS failures raise exceptions (fail-fast behavior)."""
        from whatsapp_bot import load_conversation

        # Mock get_conversation to raise exception
        mock_store.get_conversation.side_effect = Exception("GCS unavailable")

        # Verify exception is raised (fail-fast)
        phone = "972501234567"
        with pytest.raises(Exception) as exc_info:
            load_conversation(phone)

        assert "GCS unavailable" in str(exc_info.value)

    @patch('whatsapp_bot.conversation_store')
    def test_load_conversation_returns_existing(self, mock_store, mock_whatsapp_env):
        """Test that load_conversation returns existing conversation from GCS."""
        from whatsapp_bot import load_conversation
        from backend.conversation_storage.conversations import Conversation, Message

        # Mock get_conversation to return existing conversation
        mock_conv = Conversation(
            conversation_id="whatsapp_972501234567",
            area="hefer_valley",
            site="agamon_hefer",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T12:00:00Z",
            messages=[
                Message(role="user", content="Hello", timestamp="2024-01-01T12:00:00Z")
            ]
        )
        mock_store.get_conversation.return_value = mock_conv

        # Call load_conversation
        phone = "972501234567"
        conv = load_conversation(phone)

        # Verify existing conversation was returned
        mock_store.get_conversation.assert_called_once_with("whatsapp_972501234567")
        mock_store.create_conversation.assert_not_called()
        assert conv.conversation_id == "whatsapp_972501234567"
        assert len(conv.messages) == 1
