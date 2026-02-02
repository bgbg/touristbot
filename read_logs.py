#!/usr/bin/env python3
"""
Enhanced log reader for WhatsApp bot logs.

Reads and filters JSONL logs from whatsapp_logs/ directory.
Supports filtering by date, phone number, log level, and event type.
Displays logs in table format with RTL (Hebrew) support.

Usage:
  python read_logs.py
  python read_logs.py --date 2026-02-02
  python read_logs.py --phone 972525974655
  python read_logs.py --level ERROR
  python read_logs.py --event incoming_message
  python read_logs.py --source gcp  # Future: Cloud Logging support
"""

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

try:
    from bidi.algorithm import get_display
    BIDI_AVAILABLE = True
except ImportError:
    BIDI_AVAILABLE = False


def format_rtl_text(text: str) -> str:
    """Format RTL (Hebrew) text for proper terminal display."""
    if not text:
        return ""

    if BIDI_AVAILABLE:
        return get_display(text)
    else:
        # Fallback: Add RTL mark for basic support
        return "\u200f" + text


def format_time(timestamp_str: str) -> str:
    """Convert ISO timestamp to HH:MM:SS format."""
    try:
        dt = datetime.fromisoformat(timestamp_str)
        return dt.strftime("%H:%M:%S")
    except Exception:
        return "??:??:??"


def load_logs(log_file: Path, filters: dict) -> List[dict]:
    """Load and filter logs from JSONL file."""
    logs = []

    if not log_file.exists():
        return logs

    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)

                # Apply filters
                if filters.get("event") and entry.get("event_type") != filters["event"]:
                    continue

                # Phone filter (check in data.from or data.to)
                if filters.get("phone"):
                    data = entry.get("data", {})
                    phone_match = False
                    if data.get("from") and filters["phone"] in data["from"]:
                        phone_match = True
                    if data.get("to") and filters["phone"] in data["to"]:
                        phone_match = True
                    if not phone_match:
                        continue

                # Level filter (only applies to error events)
                if filters.get("level"):
                    if entry.get("event_type") != "error":
                        continue

                logs.append(entry)

            except json.JSONDecodeError:
                continue

    return logs


def print_log_table(logs: List[dict]) -> None:
    """Print logs in table format."""
    if not logs:
        print("No logs found matching criteria.")
        return

    print(f"\n{'Time':<10} {'Event':<25} {'Correlation ID':<36} {'Details'}")
    print("-" * 120)

    for log in logs:
        time = format_time(log.get("timestamp", ""))
        event = log.get("event_type", "unknown")
        corr_id = log.get("correlation_id", "")[:36] if log.get("correlation_id") else "-"
        data = log.get("data", {})

        # Format details based on event type
        details = ""
        if event == "incoming_message":
            phone = data.get("from", "unknown")
            msg_type = data.get("type", "unknown")
            details = f"From: {phone}, Type: {msg_type}"

        elif event == "outgoing_message":
            phone = data.get("to", "unknown")
            text = data.get("text", "")[:30]
            status = data.get("status", "unknown")
            details = f"To: {phone}, Status: {status}, Text: {format_rtl_text(text)}"

        elif event == "backend_request":
            area = data.get("area", "")
            site = data.get("site", "")
            query = data.get("query", "")[:30]
            details = f"Location: {area}/{site}, Query: {format_rtl_text(query)}"

        elif event == "backend_response":
            status = data.get("status", "")
            latency = data.get("latency_ms", 0)
            length = data.get("response_length", 0)
            details = f"Status: {status}, Latency: {latency:.1f}ms, Length: {length}"

        elif event == "error":
            error_type = data.get("type", "unknown")
            error_msg = data.get("error", "")[:50]
            details = f"Type: {error_type}, Error: {error_msg}"

        elif event == "status_update":
            status = data.get("status", "unknown")
            msg_id = data.get("message_id", "")[:20]
            details = f"Status: {status}, Message ID: {msg_id}"

        else:
            details = str(data)[:50]

        print(f"{time:<10} {event:<25} {corr_id:<36} {details}")


def print_summary(logs: List[dict]) -> None:
    """Print summary statistics."""
    if not logs:
        return

    # Count by event type
    event_counts = defaultdict(int)
    error_count = 0
    unique_phones = set()
    latencies = []

    for log in logs:
        event = log.get("event_type", "unknown")
        event_counts[event] += 1

        if event == "error":
            error_count += 1

        data = log.get("data", {})
        if data.get("from"):
            unique_phones.add(data["from"])
        if data.get("to"):
            unique_phones.add(data["to"])

        if event == "backend_response" and "latency_ms" in data:
            latencies.append(data["latency_ms"])

    print("\n" + "=" * 60)
    print("Summary Statistics")
    print("=" * 60)
    print(f"Total log entries: {len(logs)}")
    print(f"Unique phones: {len(unique_phones)}")
    print(f"Error count: {error_count}")

    if latencies:
        avg_latency = sum(latencies) / len(latencies)
        print(f"Average backend latency: {avg_latency:.1f}ms")

    print("\nEvent counts:")
    for event, count in sorted(event_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {event}: {count}")


def main():
    parser = argparse.ArgumentParser(description="Read and filter WhatsApp bot logs")
    parser.add_argument("--date", help="Date in YYYY-MM-DD format (default: today)")
    parser.add_argument("--phone", help="Filter by phone number")
    parser.add_argument("--level", choices=["ERROR", "WARNING", "INFO", "DEBUG"],
                        help="Filter by log level (only for error events)")
    parser.add_argument("--event", help="Filter by event type (e.g., incoming_message, backend_request)")
    parser.add_argument("--source", choices=["local", "gcp"], default="local",
                        help="Log source (local files or GCP Cloud Logging)")
    parser.add_argument("--summary", action="store_true", help="Show summary statistics")

    args = parser.parse_args()

    # Warn if source=gcp (not implemented yet)
    if args.source == "gcp":
        print("Error: GCP Cloud Logging support not implemented yet. Use --source local")
        return

    # Warn if bidi library not available
    if not BIDI_AVAILABLE:
        print("Note: python-bidi library not installed. Hebrew text may not display correctly.")
        print("  Install it with: pip install python-bidi")
        print()

    # Determine log file
    log_dir = Path("whatsapp_logs")
    if args.date:
        try:
            date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f"Error: Invalid date format. Use YYYY-MM-DD")
            return
    else:
        date = datetime.utcnow().date()

    log_file = log_dir / f"{date}.jsonl"

    if not log_file.exists():
        print(f"Log file not found: {log_file}")
        return

    # Build filters
    filters = {}
    if args.phone:
        filters["phone"] = args.phone
    if args.level:
        filters["level"] = args.level
    if args.event:
        filters["event"] = args.event

    # Load and display logs
    logs = load_logs(log_file, filters)
    print(f"\nLoading logs from: {log_file}")
    print(f"Total entries: {len(logs)}")

    if args.summary or len(logs) > 100:
        print_summary(logs)
    else:
        print_log_table(logs)
        print_summary(logs)


if __name__ == "__main__":
    main()
