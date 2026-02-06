"""
Query Logger - Logs queries to GCS as JSONL for analytics.

Appends query logs to daily files: query_logs/{YYYY-MM-DD}.jsonl
Each line is a JSON object with query metadata and response info.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

from backend.gcs_storage import StorageBackend

logger = logging.getLogger(__name__)


class QueryLogger:
    """
    Logs queries to GCS in JSONL format (one JSON object per line).

    Organizes logs by date: query_logs/{YYYY-MM-DD}.jsonl
    """

    def __init__(self, storage_backend: StorageBackend, gcs_prefix: str = "query_logs"):
        """
        Initialize query logger.

        Args:
            storage_backend: GCS storage backend
            gcs_prefix: GCS prefix for query logs (default: "query_logs")
        """
        self.storage = storage_backend
        self.gcs_prefix = gcs_prefix.rstrip("/")
        logger.info(f"QueryLogger initialized with prefix: {self.gcs_prefix}")

    def _get_log_path(self, date_str: Optional[str] = None) -> str:
        """
        Get GCS path for a log file.

        Args:
            date_str: Date string in YYYY-MM-DD format (uses today if not provided)

        Returns:
            GCS path for the log file
        """
        if not date_str:
            date_str = datetime.utcnow().strftime("%Y-%m-%d")

        return f"{self.gcs_prefix}/{date_str}.jsonl"

    def log_query(
        self,
        conversation_id: str,
        area: str,
        site: str,
        query: str,
        response_text: str,
        latency_ms: float,
        citations_count: int = 0,
        images_count: int = 0,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        error: Optional[str] = None,
        should_include_images: Optional[bool] = None,
        image_relevance: Optional[List[dict]] = None,
        citations: Optional[List[dict]] = None,
        images: Optional[List[dict]] = None,
        timing_breakdown: Optional[Dict[str, float]] = None,
    ):
        """
        Log a query to GCS.

        Appends to today's JSONL file. Failures are logged but do not raise exceptions
        (graceful degradation - logging should not break API requests).

        Args:
            conversation_id: Conversation ID
            area: Location area
            site: Location site
            query: User query text
            response_text: Assistant response text
            latency_ms: Query latency in milliseconds
            citations_count: Number of citations in response (deprecated, use citations)
            images_count: Number of images in response (deprecated, use images)
            model_name: Model used for response
            temperature: Temperature used for response
            error: Error message if query failed
            should_include_images: Boolean indicating if images should be shown
            image_relevance: List of dicts with image_uri and relevance_score
            citations: Full list of citations with source, chunk_id, text
            images: List of displayed images with uri, caption, context, relevance_score
            timing_breakdown: Dict of timing checkpoints to timestamps (milliseconds since epoch)
        """
        timestamp = datetime.utcnow().isoformat() + "Z"
        log_path = self._get_log_path()

        # Create log entry with all fields
        log_entry = {
            "timestamp": timestamp,
            "conversation_id": conversation_id,
            "area": area,
            "site": site,
            "query": query,
            "response_text": response_text,
            "response_length": len(response_text),
            "latency_ms": round(latency_ms, 2),
            "citations_count": citations_count,
            "images_count": images_count,
            "model_name": model_name,
            "temperature": temperature,
            "error": error,
        }

        # Add new structured output fields if provided
        if should_include_images is not None:
            log_entry["should_include_images"] = should_include_images

        if image_relevance is not None:
            log_entry["image_relevance"] = image_relevance

        if citations is not None:
            log_entry["citations"] = citations

        if images is not None:
            log_entry["images"] = images

        if timing_breakdown is not None:
            # Round all timing values to 2 decimal places for consistency
            log_entry["timing_breakdown"] = {
                k: round(v, 2) for k, v in timing_breakdown.items()
            }

        try:
            # Read existing content
            try:
                existing_content = self.storage.read_file(log_path)
            except FileNotFoundError:
                existing_content = ""

            # Append new log entry as JSON line
            json_line = json.dumps(log_entry, ensure_ascii=False)
            new_content = existing_content + json_line + "\n"

            # Write back to GCS
            self.storage.write_file(log_path, new_content)

            logger.debug(
                f"Logged query to {log_path}: "
                f"{conversation_id} ({area}/{site}) - {latency_ms:.0f}ms"
            )

        except Exception as e:
            # Log error but don't fail the API request
            logger.error(f"Failed to write query log to GCS: {e}")

            # Fallback: log to Cloud Logging (stderr)
            logger.warning(
                f"Query log (fallback to Cloud Logging): "
                f"{json.dumps(log_entry, ensure_ascii=False)}"
            )

    def get_logs(self, date_str: str) -> List[dict]:
        """
        Retrieve logs for a specific date.

        Args:
            date_str: Date string in YYYY-MM-DD format

        Returns:
            List of log entries (parsed JSON objects)
        """
        log_path = self._get_log_path(date_str)

        try:
            content = self.storage.read_file(log_path)
            if not content:
                return []

            # Parse JSONL (one JSON object per line)
            logs = []
            for line in content.strip().split("\n"):
                if line:
                    try:
                        logs.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        logger.warning(f"Skipping invalid JSON line: {e}")

            logger.info(f"Retrieved {len(logs)} log entries for {date_str}")
            return logs

        except FileNotFoundError:
            logger.info(f"No logs found for {date_str}")
            return []
        except Exception as e:
            logger.error(f"Error retrieving logs for {date_str}: {e}")
            return []

    def get_logs_range(self, start_date: str, end_date: str) -> List[dict]:
        """
        Retrieve logs for a date range.

        Args:
            start_date: Start date in YYYY-MM-DD format (inclusive)
            end_date: End date in YYYY-MM-DD format (inclusive)

        Returns:
            List of log entries across all dates in range
        """
        from datetime import timedelta

        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        all_logs = []
        current = start

        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            logs = self.get_logs(date_str)
            all_logs.extend(logs)
            current += timedelta(days=1)

        logger.info(
            f"Retrieved {len(all_logs)} log entries for range {start_date} to {end_date}"
        )
        return all_logs
