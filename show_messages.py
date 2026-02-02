#!/usr/bin/env python3
"""
Extract and display incoming WhatsApp text messages from webhook logs.
Includes sender name from WhatsApp profile.
Handles Hebrew (RTL) text properly.
"""

import json
from datetime import datetime
from pathlib import Path

try:
    from bidi.algorithm import get_display
    BIDI_AVAILABLE = True
except ImportError:
    BIDI_AVAILABLE = False


def extract_messages(log_file: Path) -> list[dict]:
    """Extract text messages (incoming and outgoing) from webhook log."""
    messages = []

    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)

                # Look for incoming webhook events
                if entry.get("event_type") == "incoming_webhook":
                    data = entry.get("data", {})

                    for webhook_entry in data.get("entry", []):
                        for change in webhook_entry.get("changes", []):
                            value = change.get("value", {})

                            # Extract contact name
                            contacts = value.get("contacts", [])
                            contact_name = contacts[0].get("profile", {}).get("name", "Unknown") if contacts else "Unknown"

                            # Extract messages
                            for message in value.get("messages", []):
                                msg_from = message.get("from")
                                msg_type = message.get("type")
                                timestamp = entry.get("timestamp")

                                # Format message text based on type
                                if msg_type == "text":
                                    text_body = message.get("text", {}).get("body")
                                elif msg_type == "image":
                                    caption = message.get("image", {}).get("caption", "")
                                    text_body = f"[Image{': ' + caption if caption else ''}]"
                                elif msg_type == "audio":
                                    text_body = "[Audio message]"
                                elif msg_type == "video":
                                    caption = message.get("video", {}).get("caption", "")
                                    text_body = f"[Video{': ' + caption if caption else ''}]"
                                elif msg_type == "document":
                                    filename = message.get("document", {}).get("filename", "")
                                    text_body = f"[Document{': ' + filename if filename else ''}]"
                                elif msg_type == "location":
                                    loc = message.get("location", {})
                                    name = loc.get("name", "")
                                    text_body = f"[Location{': ' + name if name else ''}]"
                                else:
                                    text_body = f"[{msg_type or 'Unknown'} message]"

                                messages.append({
                                    "timestamp": timestamp,
                                    "from": msg_from,
                                    "name": contact_name,
                                    "text": text_body,
                                    "direction": "incoming"
                                })

                # Look for outgoing messages
                elif entry.get("event_type") == "outgoing_message":
                    data = entry.get("data", {})
                    # Outgoing messages have: to, text, status, response
                    if "to" in data and "text" in data:
                        timestamp = entry.get("timestamp")
                        to = data.get("to")
                        text = data.get("text", "")

                        messages.append({
                            "timestamp": timestamp,
                            "from": "You",
                            "name": "You",
                            "text": text,
                            "to": to,
                            "direction": "outgoing"
                        })

            except (json.JSONDecodeError, KeyError) as e:
                # Skip malformed entries
                continue

    return messages


def format_time(timestamp_str: str) -> str:
    """Convert ISO timestamp to HH:MM:SS format."""
    try:
        dt = datetime.fromisoformat(timestamp_str)
        return dt.strftime("%H:%M:%S")
    except:
        return "??:??:??"


def format_rtl_text(text: str) -> str:
    """Format RTL (Hebrew) text for proper terminal display."""
    if not text:
        return ""

    if BIDI_AVAILABLE:
        # Use bidi algorithm for proper RTL display
        return get_display(text)
    else:
        # Fallback: Add RTL mark for basic support
        # U+200F is RIGHT-TO-LEFT MARK
        return "\u200f" + text


def print_table(messages: list[dict]):
    """Print messages in table format with RTL support."""
    if not messages:
        print("No messages found.")
        return

    # Print header
    print(f"{'Time':<10} {'Dir':<4} {'From/To':<15} {'Name':<20} {'Message'}")
    print("-" * 100)

    # Print messages
    for msg in messages:
        time = format_time(msg["timestamp"])
        direction = msg.get("direction", "incoming")

        # Visual indicator for direction
        if direction == "incoming":
            dir_symbol = "←"
            from_num = msg["from"] or "Unknown"
            name = msg["name"] or "Unknown"
        else:  # outgoing
            dir_symbol = "→"
            from_num = msg.get("to", "Unknown")
            name = "You"

        text = msg["text"] or ""

        # Format RTL text (Hebrew)
        name_display = format_rtl_text(name)
        text_display = format_rtl_text(text)

        # Truncate long messages (note: character count, not visual width)
        if len(text) > 50:
            text_display = format_rtl_text(text[:47]) + "..."

        # Print with proper RTL formatting
        # Note: Padding RTL text is tricky, so we just use left-aligned fields
        print(f"{time:<10} {dir_symbol:<4} {from_num:<15} {name_display:<20} {text_display}")

    print(f"\nTotal messages: {len(messages)}")


if __name__ == "__main__":
    # Warn if bidi library is not available
    if not BIDI_AVAILABLE:
        print("Note: python-bidi library not installed. Install it for better RTL text display:")
        print("  pip install python-bidi")
        print()

    log_dir = Path("whatsapp_logs")
    today = datetime.utcnow().date()
    log_file = log_dir / f"{today}.jsonl"

    if not log_file.exists():
        print(f"Log file not found: {log_file}")
        exit(1)

    messages = extract_messages(log_file)

    # Sort messages by timestamp (chronological order)
    messages.sort(key=lambda m: m["timestamp"])

    print_table(messages)
