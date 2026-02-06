"""
WhatsApp query logger - logs WhatsApp bot queries with timing data to GCS.

Wraps backend QueryLogger to log WhatsApp-specific message processing data including
detailed timing breakdowns from webhook arrival to message delivery.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Any

from backend.gcs_storage import StorageBackend
from backend.query_logging.query_logger import QueryLogger as BackendQueryLogger

logger = logging.getLogger(__name__)


class WhatsAppQueryLogger:
    """
    WhatsApp-specific query logger with timing breakdown support.

    Wraps backend QueryLogger and adds WhatsApp-specific fields like
    phone number, message_id, and detailed timing checkpoints.
    """

    def __init__(self, storage_backend: StorageBackend, gcs_prefix: str = "whatsapp_query_logs"):
        """
        Initialize WhatsApp query logger.

        Args:
            storage_backend: GCS storage backend
            gcs_prefix: GCS prefix for WhatsApp query logs (default: "whatsapp_query_logs")
        """
        self.backend_logger = BackendQueryLogger(storage_backend, gcs_prefix)
        logger.info(f"WhatsAppQueryLogger initialized with prefix: {gcs_prefix}")

    def log_query(
        self,
        conversation_id: str,
        area: str,
        site: str,
        query: str,
        response_text: str,
        latency_ms: float,
        phone: str,
        message_id: str,
        correlation_id: Optional[str] = None,
        citations: Optional[List[dict]] = None,
        images: Optional[List[dict]] = None,
        should_include_images: Optional[bool] = None,
        image_relevance: Optional[List[dict]] = None,
        timing_breakdown: Optional[Dict[str, float]] = None,
        delivery_status: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ):
        """
        Log WhatsApp query with timing data to GCS.

        Args:
            conversation_id: Conversation ID
            area: Location area
            site: Location site
            query: User query text
            response_text: Assistant response text
            latency_ms: Total query latency in milliseconds
            phone: User phone number (normalized)
            message_id: WhatsApp message ID
            correlation_id: Optional correlation ID for request tracing
            citations: Full list of citations from backend
            images: List of displayed images
            should_include_images: Boolean flag from LLM
            image_relevance: List of image relevance scores
            timing_breakdown: Dict of timing checkpoints to timestamps
            delivery_status: Optional dict with delivery confirmation timestamps
            error: Error message if query failed
        """
        # Build enhanced timing breakdown with WhatsApp-specific fields
        enhanced_timing = timing_breakdown.copy() if timing_breakdown else {}

        # Add delivery status timestamps if available
        if delivery_status:
            for status_type, timestamp in delivery_status.items():
                enhanced_timing[f"whatsapp_{status_type}"] = timestamp

        # Call backend logger with all fields
        try:
            self.backend_logger.log_query(
                conversation_id=conversation_id,
                area=area,
                site=site,
                query=query,
                response_text=response_text,
                latency_ms=latency_ms,
                citations_count=len(citations) if citations else 0,
                images_count=len(images) if images else 0,
                model_name=None,  # Not available in WhatsApp bot
                temperature=None,  # Not available in WhatsApp bot
                error=error,
                should_include_images=should_include_images,
                image_relevance=image_relevance,
                citations=citations,
                images=images,
                timing_breakdown=enhanced_timing,
            )

            logger.debug(
                f"Logged WhatsApp query: {correlation_id} - "
                f"phone={phone}, message_id={message_id}, latency={latency_ms:.0f}ms"
            )

        except Exception as e:
            # Log error but don't fail message processing
            logger.error(f"Failed to log WhatsApp query: {e}")
