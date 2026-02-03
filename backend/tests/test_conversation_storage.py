"""
Unit tests for conversation storage.
"""

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from backend.conversation_storage.conversations import (
    CONVERSATION_TIMEOUT_HOURS,
    Conversation,
    ConversationStore,
    Message,
)


class TestMessage:
    """Tests for Message dataclass."""

    def test_message_creation(self):
        """Test creating a message."""
        msg = Message(
            role="user",
            content="Hello",
            timestamp="2024-01-01T00:00:00Z",
        )
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.citations is None
        assert msg.images is None


class TestConversation:
    """Tests for Conversation dataclass."""

    def test_conversation_creation(self):
        """Test creating a conversation."""
        conv = Conversation(
            conversation_id="test-123",
            area="test_area",
            site="test_site",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            messages=[],
        )
        assert conv.conversation_id == "test-123"
        assert conv.area == "test_area"
        assert conv.site == "test_site"
        assert len(conv.messages) == 0

    def test_conversation_to_dict(self):
        """Test converting conversation to dictionary."""
        msg = Message(
            role="user", content="Hello", timestamp="2024-01-01T00:00:00Z"
        )
        conv = Conversation(
            conversation_id="test-123",
            area="test_area",
            site="test_site",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            messages=[msg],
        )

        data = conv.to_dict()
        assert data["conversation_id"] == "test-123"
        assert data["area"] == "test_area"
        assert len(data["messages"]) == 1
        assert data["messages"][0]["role"] == "user"

    def test_conversation_from_dict(self):
        """Test creating conversation from dictionary."""
        data = {
            "conversation_id": "test-123",
            "area": "test_area",
            "site": "test_site",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "messages": [
                {
                    "role": "user",
                    "content": "Hello",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "citations": None,
                    "images": None,
                }
            ],
        }

        conv = Conversation.from_dict(data)
        assert conv.conversation_id == "test-123"
        assert len(conv.messages) == 1
        assert conv.messages[0].role == "user"


class TestConversationStore:
    """Tests for ConversationStore."""

    @pytest.fixture
    def mock_storage(self):
        """Create a mock storage backend."""
        storage = MagicMock()
        return storage

    @pytest.fixture
    def store(self, mock_storage):
        """Create a conversation store with mocked storage."""
        return ConversationStore(mock_storage, gcs_prefix="test-conversations")

    def test_init(self, store):
        """Test store initialization."""
        assert store.gcs_prefix == "test-conversations"

    def test_get_gcs_path(self, store):
        """Test GCS path generation."""
        path = store._get_gcs_path("abc-123")
        assert path == "test-conversations/abc-123.json"

    def test_create_conversation(self, store):
        """Test creating a new conversation."""
        conv = store.create_conversation("area1", "site1")
        assert conv.conversation_id is not None
        assert conv.area == "area1"
        assert conv.site == "site1"
        assert len(conv.messages) == 0

    def test_create_conversation_with_id(self, store):
        """Test creating conversation with specific ID."""
        conv = store.create_conversation("area1", "site1", "custom-id")
        assert conv.conversation_id == "custom-id"

    def test_get_conversation_success(self, store, mock_storage):
        """Test loading existing conversation."""
        # Mock GCS read
        conversation_data = {
            "conversation_id": "test-123",
            "area": "area1",
            "site": "site1",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "messages": [],
        }
        mock_storage.read_file.return_value = json.dumps(conversation_data)

        conv = store.get_conversation("test-123")
        assert conv is not None
        assert conv.conversation_id == "test-123"
        assert conv.area == "area1"

        mock_storage.read_file.assert_called_once_with(
            "test-conversations/test-123.json"
        )

    def test_get_conversation_not_found(self, store, mock_storage):
        """Test loading non-existent conversation."""
        mock_storage.read_file.side_effect = FileNotFoundError()

        conv = store.get_conversation("missing-id")
        assert conv is None

    def test_get_conversation_invalid_json(self, store, mock_storage):
        """Test loading conversation with invalid JSON."""
        mock_storage.read_file.return_value = "invalid json {"

        conv = store.get_conversation("test-123")
        assert conv is None

    def test_save_conversation(self, store, mock_storage):
        """Test saving a conversation."""
        conv = Conversation(
            conversation_id="test-123",
            area="area1",
            site="site1",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            messages=[],
        )

        result = store.save_conversation(conv)
        assert result is True

        # Check that write was called
        mock_storage.write_file.assert_called_once()
        call_args = mock_storage.write_file.call_args
        assert call_args[0][0] == "test-conversations/test-123.json"
        assert "test-123" in call_args[0][1]  # JSON content

    def test_save_conversation_error(self, store, mock_storage):
        """Test save failure handling."""
        mock_storage.write_file.side_effect = Exception("Write failed")

        conv = Conversation(
            conversation_id="test-123",
            area="area1",
            site="site1",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            messages=[],
        )

        result = store.save_conversation(conv)
        assert result is False

    def test_add_message(self, store, mock_storage):
        """Test adding a message to conversation."""
        conv = store.create_conversation("area1", "site1", "test-123")

        conv = store.add_message(conv, "user", "Hello")
        assert len(conv.messages) == 1
        assert conv.messages[0].role == "user"
        assert conv.messages[0].content == "Hello"

        # Check that save was called
        mock_storage.write_file.assert_called_once()

    def test_add_message_with_citations(self, store, mock_storage):
        """Test adding message with citations and images."""
        conv = store.create_conversation("area1", "site1", "test-123")

        citations = [{"source": "doc1.txt", "chunk_id": "1"}]
        images = [{"uri": "gs://bucket/image.jpg", "caption": "Test"}]

        conv = store.add_message(
            conv, "assistant", "Response", citations=citations, images=images
        )

        assert len(conv.messages) == 1
        assert conv.messages[0].citations == citations
        assert conv.messages[0].images == images

    def test_delete_conversation(self, store, mock_storage):
        """Test deleting a conversation."""
        result = store.delete_conversation("test-123")
        assert result is True

        mock_storage.delete_file.assert_called_once_with(
            "test-conversations/test-123.json"
        )

    def test_delete_conversation_error(self, store, mock_storage):
        """Test delete failure handling."""
        mock_storage.delete_file.side_effect = Exception("Delete failed")

        result = store.delete_conversation("test-123")
        assert result is False

    def test_list_conversations(self, store, mock_storage):
        """Test listing all conversations."""
        # Mock GCS list_files
        mock_storage.list_files.return_value = [
            "test-conversations/conv_1.json",
            "test-conversations/conv_2.json",
            "test-conversations/whatsapp_123.json",
        ]

        conversation_ids = store.list_conversations()
        assert len(conversation_ids) == 3
        assert "conv_1" in conversation_ids
        assert "conv_2" in conversation_ids
        assert "whatsapp_123" in conversation_ids

    def test_list_conversations_with_prefix(self, store, mock_storage):
        """Test listing conversations with prefix filter."""
        # Mock GCS list_files
        mock_storage.list_files.return_value = [
            "test-conversations/conv_1.json",
            "test-conversations/whatsapp_123.json",
            "test-conversations/whatsapp_456.json",
        ]

        conversation_ids = store.list_conversations(prefix="whatsapp_")
        assert len(conversation_ids) == 2
        assert "whatsapp_123" in conversation_ids
        assert "whatsapp_456" in conversation_ids
        assert "conv_1" not in conversation_ids


class TestConversationExpiration:
    """Tests for conversation expiration logic."""

    @pytest.fixture
    def mock_storage(self):
        """Create a mock storage backend."""
        storage = MagicMock()
        return storage

    @pytest.fixture
    def store(self, mock_storage):
        """Create a conversation store with mocked storage."""
        return ConversationStore(mock_storage, gcs_prefix="test-conversations")

    def test_filter_expired_messages_all_recent(self, store):
        """Test filtering when all messages are recent."""
        now = datetime.utcnow()
        conv = Conversation(
            conversation_id="test-123",
            area="area1",
            site="site1",
            created_at=now.isoformat() + "Z",
            updated_at=now.isoformat() + "Z",
            messages=[
                Message(role="user", content="Hello", timestamp=now.isoformat() + "Z"),
                Message(
                    role="assistant",
                    content="Hi",
                    timestamp=(now - timedelta(hours=1)).isoformat() + "Z",
                ),
            ],
        )

        filtered_conv, expired_count = store._filter_expired_messages(conv)
        assert len(filtered_conv.messages) == 2
        assert expired_count == 0

    def test_filter_expired_messages_all_expired(self, store):
        """Test filtering when all messages are expired."""
        now = datetime.utcnow()
        old_time = now - timedelta(hours=CONVERSATION_TIMEOUT_HOURS + 1)
        conv = Conversation(
            conversation_id="test-123",
            area="area1",
            site="site1",
            created_at=old_time.isoformat() + "Z",
            updated_at=old_time.isoformat() + "Z",
            messages=[
                Message(
                    role="user",
                    content="Old message 1",
                    timestamp=old_time.isoformat() + "Z",
                ),
                Message(
                    role="assistant",
                    content="Old message 2",
                    timestamp=(old_time - timedelta(hours=1)).isoformat() + "Z",
                ),
            ],
        )

        filtered_conv, expired_count = store._filter_expired_messages(conv)
        assert len(filtered_conv.messages) == 0
        assert expired_count == 2

    def test_filter_expired_messages_mixed(self, store):
        """Test filtering with mixed old and recent messages."""
        now = datetime.utcnow()
        old_time = now - timedelta(hours=CONVERSATION_TIMEOUT_HOURS + 1)
        conv = Conversation(
            conversation_id="test-123",
            area="area1",
            site="site1",
            created_at=old_time.isoformat() + "Z",
            updated_at=now.isoformat() + "Z",
            messages=[
                Message(
                    role="user",
                    content="Old message",
                    timestamp=old_time.isoformat() + "Z",
                ),
                Message(
                    role="assistant",
                    content="Recent message",
                    timestamp=(now - timedelta(hours=1)).isoformat() + "Z",
                ),
                Message(
                    role="user",
                    content="Very recent",
                    timestamp=now.isoformat() + "Z",
                ),
            ],
        )

        filtered_conv, expired_count = store._filter_expired_messages(conv)
        assert len(filtered_conv.messages) == 2
        assert expired_count == 1
        assert filtered_conv.messages[0].content == "Recent message"
        assert filtered_conv.messages[1].content == "Very recent"

    def test_filter_expired_messages_boundary(self, store):
        """Test filtering near the 3-hour boundary."""
        now = datetime.utcnow()

        # Clearly within the window (2.5 hours old - should be kept)
        within_window = now - timedelta(hours=CONVERSATION_TIMEOUT_HOURS - 0.5)
        # Clearly past the window (4 hours old - should be filtered)
        past_window = now - timedelta(hours=CONVERSATION_TIMEOUT_HOURS + 1)

        conv = Conversation(
            conversation_id="test-123",
            area="area1",
            site="site1",
            created_at=past_window.isoformat() + "Z",
            updated_at=now.isoformat() + "Z",
            messages=[
                Message(
                    role="user",
                    content="Clearly expired (4 hours old)",
                    timestamp=past_window.isoformat() + "Z",
                ),
                Message(
                    role="assistant",
                    content="Within window (2.5 hours old)",
                    timestamp=within_window.isoformat() + "Z",
                ),
                Message(
                    role="user",
                    content="Recent",
                    timestamp=now.isoformat() + "Z",
                ),
            ],
        )

        filtered_conv, expired_count = store._filter_expired_messages(conv)
        assert len(filtered_conv.messages) == 2
        assert expired_count == 1
        assert filtered_conv.messages[0].content == "Within window (2.5 hours old)"
        assert filtered_conv.messages[1].content == "Recent"

    def test_filter_expired_messages_missing_timestamp(self, store):
        """Test backward compatibility with missing timestamps."""
        now = datetime.utcnow()
        conv = Conversation(
            conversation_id="test-123",
            area="area1",
            site="site1",
            created_at=now.isoformat() + "Z",
            updated_at=now.isoformat() + "Z",
            messages=[
                Message(
                    role="user",
                    content="Old message without timestamp",
                    timestamp=None,  # Missing timestamp
                ),
                Message(
                    role="assistant",
                    content="Recent message",
                    timestamp=now.isoformat() + "Z",
                ),
            ],
        )

        # Should not raise exception, should keep both messages
        filtered_conv, expired_count = store._filter_expired_messages(conv)
        assert len(filtered_conv.messages) == 2
        assert expired_count == 0

    def test_filter_expired_messages_invalid_timestamp(self, store):
        """Test backward compatibility with invalid timestamp format."""
        now = datetime.utcnow()
        conv = Conversation(
            conversation_id="test-123",
            area="area1",
            site="site1",
            created_at=now.isoformat() + "Z",
            updated_at=now.isoformat() + "Z",
            messages=[
                Message(
                    role="user",
                    content="Invalid timestamp",
                    timestamp="invalid-date",
                ),
                Message(
                    role="assistant",
                    content="Recent message",
                    timestamp=now.isoformat() + "Z",
                ),
            ],
        )

        # Should not raise exception, should keep both messages
        filtered_conv, expired_count = store._filter_expired_messages(conv)
        assert len(filtered_conv.messages) == 2
        assert expired_count == 0

    def test_get_conversation_applies_expiration_filter(self, store, mock_storage):
        """Test that get_conversation applies expiration filter."""
        now = datetime.utcnow()
        old_time = now - timedelta(hours=CONVERSATION_TIMEOUT_HOURS + 1)

        # Mock GCS read with conversation containing both old and recent messages
        conversation_data = {
            "conversation_id": "test-123",
            "area": "area1",
            "site": "site1",
            "created_at": old_time.isoformat() + "Z",
            "updated_at": now.isoformat() + "Z",
            "messages": [
                {
                    "role": "user",
                    "content": "Old message",
                    "timestamp": old_time.isoformat() + "Z",
                    "citations": None,
                    "images": None,
                },
                {
                    "role": "assistant",
                    "content": "Recent message",
                    "timestamp": now.isoformat() + "Z",
                    "citations": None,
                    "images": None,
                },
            ],
        }
        mock_storage.read_file.return_value = json.dumps(conversation_data)

        # Load conversation (should filter expired messages)
        conv = store.get_conversation("test-123")
        assert conv is not None
        assert len(conv.messages) == 1
        assert conv.messages[0].content == "Recent message"
