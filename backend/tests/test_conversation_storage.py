"""
Unit tests for conversation storage.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.conversation_storage.conversations import (
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
