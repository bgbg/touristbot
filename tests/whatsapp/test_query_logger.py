"""
Unit tests for WhatsApp query logger.

Tests WhatsAppQueryLogger for logging queries with timing data to GCS.
"""

from unittest.mock import Mock
import pytest

from whatsapp.query_logger import WhatsAppQueryLogger


class TestWhatsAppQueryLogger:
    """Test suite for WhatsAppQueryLogger class."""

    @pytest.fixture
    def mock_storage_backend(self):
        """Create mock storage backend."""
        return Mock()

    @pytest.fixture
    def query_logger(self, mock_storage_backend):
        """Create WhatsAppQueryLogger instance with mock storage."""
        return WhatsAppQueryLogger(mock_storage_backend, gcs_prefix="test_logs")

    def test_init_with_custom_prefix(self, mock_storage_backend):
        """Test initialization with custom GCS prefix."""
        logger = WhatsAppQueryLogger(mock_storage_backend, gcs_prefix="custom_prefix")

        assert logger.backend_logger is not None
        # Verify backend logger was initialized with correct prefix
        assert logger.backend_logger.gcs_prefix == "custom_prefix"

    def test_init_with_default_prefix(self, mock_storage_backend):
        """Test initialization with default GCS prefix."""
        logger = WhatsAppQueryLogger(mock_storage_backend)

        assert logger.backend_logger.gcs_prefix == "whatsapp_query_logs"

    def test_log_query_basic_fields(self, query_logger, mock_storage_backend):
        """Test logging query with basic required fields."""
        # Mock the backend logger's log_query method
        query_logger.backend_logger.log_query = Mock()

        query_logger.log_query(
            conversation_id="whatsapp_972501234567",
            area="עמק חפר",
            site="אגמון חפר",
            query="מה יש לראות?",
            response_text="תשובה",
            latency_ms=1234.56,
            phone="972501234567",
            message_id="wamid.123",
        )

        # Verify backend logger was called
        query_logger.backend_logger.log_query.assert_called_once()

        # Extract call arguments
        call_args = query_logger.backend_logger.log_query.call_args[1]

        assert call_args["conversation_id"] == "whatsapp_972501234567"
        assert call_args["area"] == "עמק חפר"
        assert call_args["site"] == "אגמון חפר"
        assert call_args["query"] == "מה יש לראות?"
        assert call_args["response_text"] == "תשובה"
        assert call_args["latency_ms"] == 1234.56

    def test_log_query_with_timing_breakdown(self, query_logger):
        """Test logging query with timing breakdown."""
        query_logger.backend_logger.log_query = Mock()

        timing_breakdown = {
            "webhook_received": 1705318245123.45,
            "message_processing_started": 1705318245125.89,
            "backend_request_sent": 1705318245456.45,
            "backend_response_received": 1705318255678.56,
            "text_sent": 1705318256789.23,
            "request_completed": 1705318257123.67,
        }

        query_logger.log_query(
            conversation_id="test_conv",
            area="test_area",
            site="test_site",
            query="test query",
            response_text="test response",
            latency_ms=100.0,
            phone="123456789",
            message_id="msg_123",
            timing_breakdown=timing_breakdown,
        )

        call_args = query_logger.backend_logger.log_query.call_args[1]

        # Verify timing breakdown was passed
        assert "timing_breakdown" in call_args
        assert call_args["timing_breakdown"] == timing_breakdown

    def test_log_query_with_citations(self, query_logger):
        """Test logging query with citations."""
        query_logger.backend_logger.log_query = Mock()

        citations = [
            {"source": "doc1.docx", "chunk_id": "chunk-1", "text": "citation text"},
            {"source": "doc2.docx", "chunk_id": "chunk-2", "text": "another citation"},
        ]

        query_logger.log_query(
            conversation_id="test_conv",
            area="test_area",
            site="test_site",
            query="test",
            response_text="response",
            latency_ms=100.0,
            phone="123",
            message_id="msg",
            citations=citations,
        )

        call_args = query_logger.backend_logger.log_query.call_args[1]

        assert call_args["citations"] == citations
        assert call_args["citations_count"] == 2

    def test_log_query_with_images(self, query_logger):
        """Test logging query with images."""
        query_logger.backend_logger.log_query = Mock()

        images = [
            {
                "uri": "https://storage.googleapis.com/...",
                "caption": "תמונה ראשונה",
                "context": "הקשר",
                "relevance_score": 95,
            }
        ]

        query_logger.log_query(
            conversation_id="test_conv",
            area="test_area",
            site="test_site",
            query="test",
            response_text="response",
            latency_ms=100.0,
            phone="123",
            message_id="msg",
            images=images,
            should_include_images=True,
        )

        call_args = query_logger.backend_logger.log_query.call_args[1]

        assert call_args["images"] == images
        assert call_args["images_count"] == 1
        assert call_args["should_include_images"] is True

    def test_log_query_with_image_relevance(self, query_logger):
        """Test logging query with image relevance scores."""
        query_logger.backend_logger.log_query = Mock()

        image_relevance = [
            {"image_uri": "https://...", "relevance_score": 95},
            {"image_uri": "https://...", "relevance_score": 87},
        ]

        query_logger.log_query(
            conversation_id="test_conv",
            area="test_area",
            site="test_site",
            query="test",
            response_text="response",
            latency_ms=100.0,
            phone="123",
            message_id="msg",
            image_relevance=image_relevance,
        )

        call_args = query_logger.backend_logger.log_query.call_args[1]

        assert call_args["image_relevance"] == image_relevance

    def test_log_query_with_delivery_status(self, query_logger):
        """Test logging query with delivery status timestamps."""
        query_logger.backend_logger.log_query = Mock()

        delivery_status = {
            "sent": 1705318256789.23,
            "delivered": 1705318258123.45,
            "read": 1705318260000.00,
        }

        timing_breakdown = {
            "webhook_received": 1705318245123.45,
            "text_sent": 1705318256789.23,
        }

        query_logger.log_query(
            conversation_id="test_conv",
            area="test_area",
            site="test_site",
            query="test",
            response_text="response",
            latency_ms=100.0,
            phone="123",
            message_id="msg",
            timing_breakdown=timing_breakdown,
            delivery_status=delivery_status,
        )

        call_args = query_logger.backend_logger.log_query.call_args[1]

        # Verify delivery status was merged into timing breakdown
        enhanced_timing = call_args["timing_breakdown"]
        assert "whatsapp_sent" in enhanced_timing
        assert "whatsapp_delivered" in enhanced_timing
        assert "whatsapp_read" in enhanced_timing
        assert enhanced_timing["whatsapp_sent"] == 1705318256789.23
        assert enhanced_timing["whatsapp_delivered"] == 1705318258123.45
        assert enhanced_timing["whatsapp_read"] == 1705318260000.00

        # Verify original timing breakdown was preserved
        assert enhanced_timing["webhook_received"] == 1705318245123.45
        assert enhanced_timing["text_sent"] == 1705318256789.23

    def test_log_query_with_error(self, query_logger):
        """Test logging query with error message."""
        query_logger.backend_logger.log_query = Mock()

        query_logger.log_query(
            conversation_id="test_conv",
            area="test_area",
            site="test_site",
            query="test",
            response_text="error response",
            latency_ms=50.0,
            phone="123",
            message_id="msg",
            error="Backend API timeout",
        )

        call_args = query_logger.backend_logger.log_query.call_args[1]

        assert call_args["error"] == "Backend API timeout"

    def test_log_query_with_correlation_id(self, query_logger):
        """Test logging query with correlation ID."""
        query_logger.backend_logger.log_query = Mock()

        query_logger.log_query(
            conversation_id="test_conv",
            area="test_area",
            site="test_site",
            query="test",
            response_text="response",
            latency_ms=100.0,
            phone="123",
            message_id="msg",
            correlation_id="uuid-test-456",
        )

        # Correlation ID is used for debug logging (not stored in GCS)
        # Just verify the call succeeded
        query_logger.backend_logger.log_query.assert_called_once()

    def test_log_query_model_and_temperature_are_none(self, query_logger):
        """Test that model_name and temperature are set to None for WhatsApp."""
        query_logger.backend_logger.log_query = Mock()

        query_logger.log_query(
            conversation_id="test_conv",
            area="test_area",
            site="test_site",
            query="test",
            response_text="response",
            latency_ms=100.0,
            phone="123",
            message_id="msg",
        )

        call_args = query_logger.backend_logger.log_query.call_args[1]

        # WhatsApp bot doesn't have model/temperature info (backend API handles it)
        assert call_args["model_name"] is None
        assert call_args["temperature"] is None

    def test_log_query_exception_handling(self, query_logger):
        """Test that exceptions during logging don't crash the application."""
        # Make backend logger raise an exception
        query_logger.backend_logger.log_query = Mock(
            side_effect=Exception("GCS write failed")
        )

        # This should not raise an exception (graceful degradation)
        try:
            query_logger.log_query(
                conversation_id="test_conv",
                area="test_area",
                site="test_site",
                query="test",
                response_text="response",
                latency_ms=100.0,
                phone="123",
                message_id="msg",
            )
        except Exception:
            pytest.fail("log_query() should not raise exceptions")

    def test_log_query_empty_timing_breakdown(self, query_logger):
        """Test logging with empty timing breakdown."""
        query_logger.backend_logger.log_query = Mock()

        query_logger.log_query(
            conversation_id="test_conv",
            area="test_area",
            site="test_site",
            query="test",
            response_text="response",
            latency_ms=100.0,
            phone="123",
            message_id="msg",
            timing_breakdown={},
        )

        call_args = query_logger.backend_logger.log_query.call_args[1]

        assert call_args["timing_breakdown"] == {}

    def test_log_query_none_timing_breakdown(self, query_logger):
        """Test logging with None timing breakdown."""
        query_logger.backend_logger.log_query = Mock()

        query_logger.log_query(
            conversation_id="test_conv",
            area="test_area",
            site="test_site",
            query="test",
            response_text="response",
            latency_ms=100.0,
            phone="123",
            message_id="msg",
            timing_breakdown=None,
        )

        call_args = query_logger.backend_logger.log_query.call_args[1]

        # Should create empty dict
        assert call_args["timing_breakdown"] == {}

    def test_log_query_complete_realistic_scenario(self, query_logger):
        """Test complete realistic logging scenario with all fields."""
        query_logger.backend_logger.log_query = Mock()

        timing_breakdown = {
            "webhook_received": 1705318245123.45,
            "background_task_started": 1705318245125.12,
            "message_processing_started": 1705318245125.89,
            "conversation_loaded": 1705318245234.56,
            "user_message_saved": 1705318245456.23,
            "backend_request_sent": 1705318245456.45,
            "backend_api_call_start": 1705318245457.12,
            "backend_api_call_end": 1705318255678.34,
            "backend_response_received": 1705318255678.56,
            "text_sent": 1705318256789.23,
            "history_saved": 1705318257123.45,
            "request_completed": 1705318257123.67,
        }

        citations = [
            {"source": "agamon_hefer.docx", "text": "אגמון חפר הוא שמורת טבע"}
        ]

        images = [
            {
                "uri": "https://storage.googleapis.com/bucket/image_001.jpg",
                "caption": "שקנאים באגמון",
                "relevance_score": 92,
            }
        ]

        image_relevance = [
            {"image_uri": "https://.../image_001.jpg", "relevance_score": 92},
            {"image_uri": "https://.../image_002.jpg", "relevance_score": 78},
        ]

        query_logger.log_query(
            conversation_id="whatsapp_972501234567",
            area="עמק חפר",
            site="אגמון חפר",
            query="מה יש לראות באגמון חפר?",
            response_text="באגמון חפר תוכלו לראות מגוון רחב של עופות מים...",
            latency_ms=11998.22,
            phone="972501234567",
            message_id="wamid.ABC123",
            correlation_id="uuid-def-456",
            citations=citations,
            images=images,
            should_include_images=True,
            image_relevance=image_relevance,
            timing_breakdown=timing_breakdown,
            error=None,
        )

        # Verify call succeeded
        query_logger.backend_logger.log_query.assert_called_once()

        call_args = query_logger.backend_logger.log_query.call_args[1]

        # Verify all fields were passed correctly
        assert call_args["conversation_id"] == "whatsapp_972501234567"
        assert call_args["latency_ms"] == 11998.22
        assert call_args["citations_count"] == 1
        assert call_args["images_count"] == 1
        assert call_args["should_include_images"] is True
        assert len(call_args["timing_breakdown"]) == 12
        assert call_args["error"] is None
