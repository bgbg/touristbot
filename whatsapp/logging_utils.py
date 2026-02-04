"""
Event logging utilities for WhatsApp bot.

Provides structured logging to daily JSONL files and stderr output.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any


class EventLogger:
    """
    Event logger for structured logging to daily JSONL files.

    Logs events to daily files in format: {timestamp, event_type, correlation_id, data}
    Also echoes events to stderr for real-time monitoring.
    """

    def __init__(self, log_dir: Path):
        """
        Initialize event logger.

        Args:
            log_dir: Directory for log files (created if doesn't exist)
        """
        self.log_dir = log_dir
        self.log_dir.mkdir(exist_ok=True)

    def log_event(
        self,
        event_type: str,
        data: dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Log event to daily JSONL file and stderr.

        Args:
            event_type: Event type identifier (e.g., "incoming_message", "error")
            data: Event data dictionary
            correlation_id: Optional correlation ID for request tracing
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        log_entry = {
            "timestamp": timestamp,
            "event_type": event_type,
            "correlation_id": correlation_id,
            "data": data,
        }

        # Log to daily file
        log_file = self.log_dir / f"{datetime.now(timezone.utc).date()}.jsonl"
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            self.eprint(f"[ERROR] Failed to write log: {e}")

        # Also print to console
        self.eprint(f"[{timestamp}] {event_type}")
        if event_type == "error":
            self.eprint(json.dumps(data, ensure_ascii=False, indent=2))

    def eprint(self, *args: object) -> None:
        """
        Print to stderr for real-time monitoring.

        Args:
            *args: Values to print (same as print())
        """
        print(*args, file=sys.stderr)


def eprint(*args: object) -> None:
    """
    Standalone utility to print to stderr.

    Args:
        *args: Values to print (same as print())
    """
    print(*args, file=sys.stderr)
