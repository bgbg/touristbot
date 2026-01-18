"""
Unit tests for query logger.
"""

import json
from datetime import datetime
from unittest.mock import MagicMock, call

import pytest

from backend.query_logging.query_logger import QueryLogger


class TestQueryLogger:
    """Tests for QueryLogger."""

    @pytest.fixture
    def mock_storage(self):
        """Create a mock storage backend."""
        storage = MagicMock()
        return storage

    @pytest.fixture
    def logger(self, mock_storage):
        """Create a query logger with mocked storage."""
        return QueryLogger(mock_storage, gcs_prefix="test-logs")

    def test_init(self, logger):
        """Test logger initialization."""
        assert logger.gcs_prefix == "test-logs"

    def test_get_log_path_today(self, logger):
        """Test log path generation for today."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        path = logger._get_log_path()
        assert path == f"test-logs/{today}.jsonl"

    def test_get_log_path_specific_date(self, logger):
        """Test log path generation for specific date."""
        path = logger._get_log_path("2024-01-15")
        assert path == "test-logs/2024-01-15.jsonl"

    def test_log_query_new_file(self, logger, mock_storage):
        """Test logging to a new file."""
        # Mock: file doesn't exist yet
        mock_storage.read_file.side_effect = FileNotFoundError()

        logger.log_query(
            conversation_id="conv-123",
            area="area1",
            site="site1",
            query="What is this place?",
            response_text="This is a museum.",
            latency_ms=1234.56,
            citations_count=3,
            images_count=2,
            model_name="gemini-2.0-flash",
            temperature=0.7,
        )

        # Check that write was called
        mock_storage.write_file.assert_called_once()
        call_args = mock_storage.write_file.call_args

        # Check path
        log_path = call_args[0][0]
        assert log_path.startswith("test-logs/")
        assert log_path.endswith(".jsonl")

        # Check content
        content = call_args[0][1]
        lines = content.strip().split("\n")
        assert len(lines) == 1  # Single log entry

        # Parse JSON
        log_entry = json.loads(lines[0])
        assert log_entry["conversation_id"] == "conv-123"
        assert log_entry["area"] == "area1"
        assert log_entry["query"] == "What is this place?"
        assert log_entry["latency_ms"] == 1234.56
        assert log_entry["citations_count"] == 3
        assert log_entry["model_name"] == "gemini-2.0-flash"

    def test_log_query_append_to_existing(self, logger, mock_storage):
        """Test appending to existing log file."""
        # Mock: file exists with one entry
        existing_log = json.dumps({"timestamp": "2024-01-01T00:00:00Z", "query": "old"})
        mock_storage.read_file.return_value = existing_log + "\n"

        logger.log_query(
            conversation_id="conv-456",
            area="area2",
            site="site2",
            query="New query",
            response_text="New response",
            latency_ms=500.0,
        )

        # Check that write was called
        call_args = mock_storage.write_file.call_args
        content = call_args[0][1]
        lines = content.strip().split("\n")
        assert len(lines) == 2  # Old entry + new entry

        # Parse both entries
        old_entry = json.loads(lines[0])
        new_entry = json.loads(lines[1])
        assert old_entry["query"] == "old"
        assert new_entry["query"] == "New query"

    def test_log_query_with_error(self, logger, mock_storage):
        """Test logging a failed query."""
        mock_storage.read_file.side_effect = FileNotFoundError()

        logger.log_query(
            conversation_id="conv-789",
            area="area3",
            site="site3",
            query="Bad query",
            response_text="",
            latency_ms=100.0,
            error="API error: timeout",
        )

        call_args = mock_storage.write_file.call_args
        content = call_args[0][1]
        log_entry = json.loads(content.strip())

        assert log_entry["error"] == "API error: timeout"
        assert log_entry["response_text"] == ""

    def test_log_query_write_failure_graceful(self, logger, mock_storage):
        """Test that write failures don't raise exceptions."""
        mock_storage.read_file.side_effect = FileNotFoundError()
        mock_storage.write_file.side_effect = Exception("GCS write failed")

        # Should not raise exception
        logger.log_query(
            conversation_id="conv-fail",
            area="area",
            site="site",
            query="Query",
            response_text="Response",
            latency_ms=100.0,
        )

        # Write was attempted
        mock_storage.write_file.assert_called_once()

    def test_get_logs_success(self, logger, mock_storage):
        """Test retrieving logs for a date."""
        # Mock: file with multiple entries
        log_lines = [
            json.dumps({"timestamp": "2024-01-15T10:00:00Z", "query": "query1"}),
            json.dumps({"timestamp": "2024-01-15T11:00:00Z", "query": "query2"}),
            json.dumps({"timestamp": "2024-01-15T12:00:00Z", "query": "query3"}),
        ]
        mock_storage.read_file.return_value = "\n".join(log_lines) + "\n"

        logs = logger.get_logs("2024-01-15")

        assert len(logs) == 3
        assert logs[0]["query"] == "query1"
        assert logs[1]["query"] == "query2"
        assert logs[2]["query"] == "query3"

        mock_storage.read_file.assert_called_once_with("test-logs/2024-01-15.jsonl")

    def test_get_logs_not_found(self, logger, mock_storage):
        """Test retrieving logs for date with no logs."""
        mock_storage.read_file.side_effect = FileNotFoundError()

        logs = logger.get_logs("2024-01-01")

        assert logs == []

    def test_get_logs_invalid_json_line(self, logger, mock_storage):
        """Test handling invalid JSON lines gracefully."""
        log_lines = [
            json.dumps({"query": "valid1"}),
            "invalid json line {",
            json.dumps({"query": "valid2"}),
        ]
        mock_storage.read_file.return_value = "\n".join(log_lines)

        logs = logger.get_logs("2024-01-15")

        # Should return only valid entries
        assert len(logs) == 2
        assert logs[0]["query"] == "valid1"
        assert logs[1]["query"] == "valid2"

    def test_get_logs_range(self, logger, mock_storage):
        """Test retrieving logs for a date range."""

        def mock_read(path):
            """Mock read that returns data based on date."""
            if "2024-01-15" in path:
                return json.dumps({"query": "day1"}) + "\n"
            elif "2024-01-16" in path:
                return json.dumps({"query": "day2"}) + "\n"
            elif "2024-01-17" in path:
                return json.dumps({"query": "day3"}) + "\n"
            else:
                raise FileNotFoundError()

        mock_storage.read_file.side_effect = mock_read

        logs = logger.get_logs_range("2024-01-15", "2024-01-17")

        assert len(logs) == 3
        assert logs[0]["query"] == "day1"
        assert logs[1]["query"] == "day2"
        assert logs[2]["query"] == "day3"

    def test_log_query_hebrew_content(self, logger, mock_storage):
        """Test logging with Hebrew UTF-8 content."""
        mock_storage.read_file.side_effect = FileNotFoundError()

        logger.log_query(
            conversation_id="conv-hebrew",
            area="hefer_valley",
            site="agamon_hefer",
            query="מה זה המקום הזה?",
            response_text="זהו אגמון חפר, שמורת טבע יפהפייה.",
            latency_ms=1500.0,
            citations_count=1,
        )

        call_args = mock_storage.write_file.call_args
        content = call_args[0][1]
        log_entry = json.loads(content.strip())

        # Hebrew should be preserved
        assert log_entry["query"] == "מה זה המקום הזה?"
        assert log_entry["response_text"] == "זהו אגמון חפר, שמורת טבע יפהפייה."

    def test_log_query_with_structured_output_fields(self, logger, mock_storage):
        """Test logging with all new structured output fields."""
        mock_storage.read_file.side_effect = FileNotFoundError()

        citations = [
            {
                "source": "document.docx",
                "chunk_id": "chunk-123",
                "text": "Some text from document",
            },
            {
                "source": "other-doc.pdf",
                "chunk_id": "chunk-456",
                "text": "More text",
            },
        ]

        image_relevance = [
            {
                "image_uri": "https://generativelanguage.googleapis.com/v1beta/files/abc123",
                "relevance_score": 85,
            },
            {
                "image_uri": "https://generativelanguage.googleapis.com/v1beta/files/def456",
                "relevance_score": 60,
            },
        ]

        images = [
            {
                "uri": "https://storage.googleapis.com/bucket/image1.jpg",
                "file_api_uri": "https://generativelanguage.googleapis.com/v1beta/files/abc123",
                "caption": "Beautiful landscape",
                "context": "This shows the main area",
                "relevance_score": 85,
            }
        ]

        logger.log_query(
            conversation_id="conv-structured",
            area="test_area",
            site="test_site",
            query="Show me images of birds",
            response_text="Here are some bird images.",
            latency_ms=2000.0,
            citations_count=2,
            images_count=1,
            model_name="gemini-2.5-flash",
            temperature=0.6,
            should_include_images=True,
            image_relevance=image_relevance,
            citations=citations,
            images=images,
        )

        call_args = mock_storage.write_file.call_args
        content = call_args[0][1]
        log_entry = json.loads(content.strip())

        # Verify all structured fields are present
        assert log_entry["should_include_images"] is True
        assert len(log_entry["image_relevance"]) == 2
        assert log_entry["image_relevance"][0]["relevance_score"] == 85
        assert len(log_entry["citations"]) == 2
        assert log_entry["citations"][0]["source"] == "document.docx"
        assert len(log_entry["images"]) == 1
        assert log_entry["images"][0]["caption"] == "Beautiful landscape"

    def test_log_query_backward_compatibility(self, logger, mock_storage):
        """Test that old calls without new fields still work."""
        mock_storage.read_file.side_effect = FileNotFoundError()

        # Call without any of the new optional fields
        logger.log_query(
            conversation_id="conv-old",
            area="area1",
            site="site1",
            query="Old style query",
            response_text="Old style response",
            latency_ms=100.0,
        )

        call_args = mock_storage.write_file.call_args
        content = call_args[0][1]
        log_entry = json.loads(content.strip())

        # Should have basic fields
        assert log_entry["query"] == "Old style query"
        assert log_entry["response_text"] == "Old style response"
        # New fields should not be present
        assert "should_include_images" not in log_entry
        assert "image_relevance" not in log_entry
        assert "citations" not in log_entry
        assert "images" not in log_entry

    def test_log_query_partial_structured_fields(self, logger, mock_storage):
        """Test logging with only some structured fields populated."""
        mock_storage.read_file.side_effect = FileNotFoundError()

        # Only provide should_include_images and citations
        logger.log_query(
            conversation_id="conv-partial",
            area="area1",
            site="site1",
            query="Partial query",
            response_text="Partial response",
            latency_ms=500.0,
            should_include_images=False,
            citations=[{"source": "doc.txt", "chunk_id": "123", "text": "text"}],
        )

        call_args = mock_storage.write_file.call_args
        content = call_args[0][1]
        log_entry = json.loads(content.strip())

        # Should have provided fields
        assert log_entry["should_include_images"] is False
        assert len(log_entry["citations"]) == 1
        # Other fields should not be present
        assert "image_relevance" not in log_entry
        assert "images" not in log_entry

    def test_log_query_empty_structured_lists(self, logger, mock_storage):
        """Test logging with empty lists for structured fields."""
        mock_storage.read_file.side_effect = FileNotFoundError()

        logger.log_query(
            conversation_id="conv-empty",
            area="area1",
            site="site1",
            query="Query with no results",
            response_text="No results found",
            latency_ms=200.0,
            should_include_images=False,
            image_relevance=[],
            citations=[],
            images=[],
        )

        call_args = mock_storage.write_file.call_args
        content = call_args[0][1]
        log_entry = json.loads(content.strip())

        # Empty lists should be present in log
        assert log_entry["should_include_images"] is False
        assert log_entry["image_relevance"] == []
        assert log_entry["citations"] == []
        assert log_entry["images"] == []

    def test_log_query_complex_nested_structures(self, logger, mock_storage):
        """Test JSON serialization of complex nested structures."""
        mock_storage.read_file.side_effect = FileNotFoundError()

        # Complex nested structure with Hebrew text
        citations = [
            {
                "source": "hebrew-doc.docx",
                "chunk_id": "chunk-789",
                "text": "טקסט בעברית עם ציטוט מהמסמך המקורי",
            }
        ]

        images = [
            {
                "uri": "https://storage.googleapis.com/bucket/image.jpg",
                "file_api_uri": "https://generativelanguage.googleapis.com/file",
                "caption": "כיתוב בעברית",
                "context": "הקשר לפני התמונה. הקשר אחרי התמונה.",
                "relevance_score": 95,
            }
        ]

        logger.log_query(
            conversation_id="conv-complex",
            area="hefer_valley",
            site="agamon_hefer",
            query="שאלה מורכבת עם עברית",
            response_text="תשובה מורכבת",
            latency_ms=3000.0,
            citations=citations,
            images=images,
        )

        call_args = mock_storage.write_file.call_args
        content = call_args[0][1]
        log_entry = json.loads(content.strip())

        # Verify complex structures are preserved
        assert log_entry["citations"][0]["text"] == "טקסט בעברית עם ציטוט מהמסמך המקורי"
        assert log_entry["images"][0]["caption"] == "כיתוב בעברית"
        assert "הקשר לפני" in log_entry["images"][0]["context"]
