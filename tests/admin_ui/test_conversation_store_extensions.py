"""Tests for ConversationStore extensions (list, bulk delete, stats)."""

import json
import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime

from backend.conversation_storage.conversations import ConversationStore, Conversation, Message


@pytest.fixture
def mock_storage():
    """Create a mock storage backend."""
    storage = Mock()
    return storage


@pytest.fixture
def store(mock_storage):
    """Create a ConversationStore with mock storage."""
    return ConversationStore(mock_storage, gcs_prefix="test-conversations")


def create_mock_conversation_data(
    conversation_id: str,
    area: str,
    site: str,
    message_count: int = 3,
    created_at: str = "2024-01-01T00:00:00Z",
    updated_at: str = "2024-01-01T01:00:00Z",
) -> str:
    """Helper to create mock conversation JSON data."""
    messages = []
    for i in range(message_count):
        role = "user" if i % 2 == 0 else "assistant"
        messages.append({
            "role": role,
            "content": f"Message {i+1}",
            "timestamp": f"2024-01-01T00:{i:02d}:00Z",
        })

    data = {
        "conversation_id": conversation_id,
        "area": area,
        "site": site,
        "created_at": created_at,
        "updated_at": updated_at,
        "messages": messages,
    }
    return json.dumps(data)


class TestListAllConversations:
    """Tests for list_all_conversations method."""

    def test_list_all_conversations_no_filters(self, store, mock_storage):
        """Test listing all conversations without filters."""
        # Setup mock
        mock_storage.list_files.return_value = [
            "test-conversations/conv1.json",
            "test-conversations/conv2.json",
        ]
        mock_storage.read_file.side_effect = [
            create_mock_conversation_data("conv1", "area1", "site1", 2),
            create_mock_conversation_data("conv2", "area2", "site2", 3),
        ]

        # Call method
        result = store.list_all_conversations()

        # Assertions
        assert len(result) == 2
        assert result[0]["conversation_id"] in ["conv1", "conv2"]
        assert result[0]["message_count"] in [2, 3]
        mock_storage.list_files.assert_called_once_with("test-conversations", "*.json")

    def test_list_all_conversations_with_area_filter(self, store, mock_storage):
        """Test filtering conversations by area."""
        mock_storage.list_files.return_value = [
            "test-conversations/conv1.json",
            "test-conversations/conv2.json",
        ]
        mock_storage.read_file.side_effect = [
            create_mock_conversation_data("conv1", "area1", "site1"),
            create_mock_conversation_data("conv2", "area2", "site2"),
        ]

        result = store.list_all_conversations(area_filter="area1")

        assert len(result) == 1
        assert result[0]["area"] == "area1"

    def test_list_all_conversations_with_site_filter(self, store, mock_storage):
        """Test filtering conversations by site."""
        mock_storage.list_files.return_value = [
            "test-conversations/conv1.json",
            "test-conversations/conv2.json",
        ]
        mock_storage.read_file.side_effect = [
            create_mock_conversation_data("conv1", "area1", "site1"),
            create_mock_conversation_data("conv2", "area1", "site2"),
        ]

        result = store.list_all_conversations(site_filter="site1")

        assert len(result) == 1
        assert result[0]["site"] == "site1"

    def test_list_all_conversations_with_date_filter(self, store, mock_storage):
        """Test filtering conversations by date range."""
        mock_storage.list_files.return_value = [
            "test-conversations/conv1.json",
            "test-conversations/conv2.json",
        ]
        mock_storage.read_file.side_effect = [
            create_mock_conversation_data(
                "conv1", "area1", "site1", created_at="2024-01-01T00:00:00Z"
            ),
            create_mock_conversation_data(
                "conv2", "area1", "site1", created_at="2024-01-15T00:00:00Z"
            ),
        ]

        result = store.list_all_conversations(start_date="2024-01-10T00:00:00Z")

        assert len(result) == 1
        assert result[0]["conversation_id"] == "conv2"

    def test_list_all_conversations_with_limit(self, store, mock_storage):
        """Test limiting number of returned conversations."""
        mock_storage.list_files.return_value = [
            f"test-conversations/conv{i}.json" for i in range(5)
        ]
        mock_storage.read_file.side_effect = [
            create_mock_conversation_data(f"conv{i}", "area1", "site1")
            for i in range(5)
        ]

        result = store.list_all_conversations(limit=2)

        assert len(result) == 2

    def test_list_all_conversations_sorts_by_updated_at(self, store, mock_storage):
        """Test conversations are sorted by updated_at DESC."""
        mock_storage.list_files.return_value = [
            "test-conversations/conv1.json",
            "test-conversations/conv2.json",
        ]
        mock_storage.read_file.side_effect = [
            create_mock_conversation_data(
                "conv1", "area1", "site1", updated_at="2024-01-01T00:00:00Z"
            ),
            create_mock_conversation_data(
                "conv2", "area1", "site1", updated_at="2024-01-02T00:00:00Z"
            ),
        ]

        result = store.list_all_conversations()

        assert result[0]["conversation_id"] == "conv2"  # Most recent first
        assert result[1]["conversation_id"] == "conv1"

    def test_list_all_conversations_extracts_last_query(self, store, mock_storage):
        """Test extraction of last user message."""
        messages_data = {
            "conversation_id": "conv1",
            "area": "area1",
            "site": "site1",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T01:00:00Z",
            "messages": [
                {"role": "user", "content": "Hello", "timestamp": "2024-01-01T00:00:00Z"},
                {"role": "assistant", "content": "Hi", "timestamp": "2024-01-01T00:01:00Z"},
                {"role": "user", "content": "What's the weather?", "timestamp": "2024-01-01T00:02:00Z"},
            ],
        }

        mock_storage.list_files.return_value = ["test-conversations/conv1.json"]
        mock_storage.read_file.return_value = json.dumps(messages_data)

        result = store.list_all_conversations()

        assert result[0]["last_query"] == "What's the weather?"

    def test_list_all_conversations_handles_errors(self, store, mock_storage):
        """Test graceful handling of corrupted conversation files."""
        mock_storage.list_files.return_value = [
            "test-conversations/conv1.json",
            "test-conversations/conv2.json",
        ]
        mock_storage.read_file.side_effect = [
            "invalid json",  # Corrupt file
            create_mock_conversation_data("conv2", "area1", "site1"),
        ]

        result = store.list_all_conversations()

        # Should skip corrupt file and return valid one
        assert len(result) == 1
        assert result[0]["conversation_id"] == "conv2"

    def test_list_all_conversations_empty_bucket(self, store, mock_storage):
        """Test handling of empty bucket."""
        mock_storage.list_files.return_value = []

        result = store.list_all_conversations()

        assert result == []


class TestDeleteConversationsBulk:
    """Tests for delete_conversations_bulk method."""

    def test_delete_conversations_bulk_all_success(self, store, mock_storage):
        """Test bulk delete when all succeed."""
        mock_storage.delete_file.return_value = True

        result = store.delete_conversations_bulk(["conv1", "conv2", "conv3"])

        assert result["success_count"] == 3
        assert result["failed_count"] == 0
        assert result["failed_ids"] == []
        assert mock_storage.delete_file.call_count == 3

    def test_delete_conversations_bulk_partial_failure(self, store, mock_storage):
        """Test bulk delete with some failures."""
        # First two succeed, third fails
        mock_storage.delete_file.side_effect = [True, True, Exception("Delete failed")]

        result = store.delete_conversations_bulk(["conv1", "conv2", "conv3"])

        assert result["success_count"] == 2
        assert result["failed_count"] == 1
        assert "conv3" in result["failed_ids"]

    def test_delete_conversations_bulk_all_fail(self, store, mock_storage):
        """Test bulk delete when all fail."""
        mock_storage.delete_file.side_effect = Exception("GCS error")

        result = store.delete_conversations_bulk(["conv1", "conv2"])

        assert result["success_count"] == 0
        assert result["failed_count"] == 2
        assert set(result["failed_ids"]) == {"conv1", "conv2"}

    def test_delete_conversations_bulk_empty_list(self, store, mock_storage):
        """Test bulk delete with empty list."""
        result = store.delete_conversations_bulk([])

        assert result["success_count"] == 0
        assert result["failed_count"] == 0
        assert result["failed_ids"] == []
        mock_storage.delete_file.assert_not_called()


class TestGetConversationsStats:
    """Tests for get_conversations_stats method."""

    def test_get_conversations_stats(self, store, mock_storage):
        """Test getting conversation statistics."""
        mock_storage.list_files.return_value = [
            "test-conversations/conv1.json",
            "test-conversations/conv2.json",
            "test-conversations/conv3.json",
        ]
        mock_storage.read_file.side_effect = [
            create_mock_conversation_data(
                "conv1", "area1", "site1", created_at="2024-01-01T00:00:00Z"
            ),
            create_mock_conversation_data(
                "conv2", "area1", "site2", created_at="2024-01-02T00:00:00Z"
            ),
            create_mock_conversation_data(
                "conv3", "area2", "site1", created_at="2024-01-03T00:00:00Z"
            ),
        ]

        result = store.get_conversations_stats()

        assert result["total_conversations"] == 3
        assert result["by_area"]["area1"] == 2
        assert result["by_area"]["area2"] == 1
        assert result["by_site"]["area1/site1"] == 1
        assert result["by_site"]["area1/site2"] == 1
        assert result["by_site"]["area2/site1"] == 1
        assert result["date_range"]["earliest"] == "2024-01-01T00:00:00Z"
        assert result["date_range"]["latest"] == "2024-01-03T00:00:00Z"

    def test_get_conversations_stats_empty(self, store, mock_storage):
        """Test stats with no conversations."""
        mock_storage.list_files.return_value = []

        result = store.get_conversations_stats()

        assert result["total_conversations"] == 0
        assert result["by_area"] == {}
        assert result["by_site"] == {}
        assert result["date_range"]["earliest"] is None
        assert result["date_range"]["latest"] is None

    def test_get_conversations_stats_handles_errors(self, store, mock_storage):
        """Test stats handles errors gracefully."""
        mock_storage.list_files.side_effect = Exception("GCS error")

        result = store.get_conversations_stats()

        assert result["total_conversations"] == 0
        assert result["by_area"] == {}
