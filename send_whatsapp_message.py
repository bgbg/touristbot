#!/usr/bin/env python3
"""
Send a WhatsApp message via Meta WhatsApp Cloud API.

Env vars expected:
  WHATSAPP_ACCESS_TOKEN
  WHATSAPP_PHONE_NUMBER_ID

Usage:
  # Send text message only
  python try_whatsapp.py 972525974655 --text "Hello!"

  # Send image without caption
  python try_whatsapp.py 972525974655 --image path/to/image.jpg

  # Send image with caption
  python try_whatsapp.py 972525974655 --image path/to/image.jpg --text "Check this out!"
"""

from __future__ import annotations

import defopt
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Import WhatsApp utility functions
from whatsapp_utils import (
    normalize_msisdn,
    upload_media,
    send_text_message,
    send_image_message,
)

load_dotenv()

# Logging directory (same as whatsapp_bot.py)
LOG_DIR = Path("whatsapp_logs")
LOG_DIR.mkdir(exist_ok=True)


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def log_event(event_type: str, data: dict) -> None:
    """Log event to daily JSONL file (same format as whatsapp_bot.py)."""
    timestamp = datetime.now(timezone.utc).isoformat()
    log_entry = {
        "timestamp": timestamp,
        "event_type": event_type,
        "data": data,
    }

    # Log to daily file
    log_file = LOG_DIR / f"{datetime.now(timezone.utc).date()}.jsonl"
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        eprint(f"[ERROR] Failed to write log: {e}")


def main(
    *,
    to: str,
    text: Optional[str] = None,
    image: Optional[str] = None,
) -> int:
    """Send a WhatsApp message via Meta WhatsApp Cloud API.

    :param to: Destination MSISDN (e.g. 972525974655 or +972525974655)
    :param text: Message text (for text-only) or caption (when used with --image)
    :param image: Path to image file to send
    """
    # Validate arguments
    if not text and not image:
        eprint("Error: Either --text or --image must be provided")
        return 2

    token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

    if not token:
        eprint("Missing env var: WHATSAPP_ACCESS_TOKEN")
        return 2
    if not phone_number_id:
        eprint("Missing env var: WHATSAPP_PHONE_NUMBER_ID")
        return 2

    to_msisdn = normalize_msisdn(to)

    eprint(f"Using token: {token[:4]}...{token[-4:]}")
    eprint(f"Using phone number ID: {phone_number_id}")
    eprint(f"Sending to: {to_msisdn}")

    if image:
        # Upload image and send (text becomes caption)
        eprint(f"Uploading image: {image}")
        status, resp_json = upload_media(token, phone_number_id, image)

        if 200 <= status < 300 and "id" in resp_json:
            media_id = resp_json["id"]
            eprint(f"✓ Upload successful! Media ID: {media_id}")

            caption_msg = f" with caption: {text}" if text else ""
            eprint(f"Sending image message{caption_msg}...")
            status, resp_json = send_image_message(
                token, phone_number_id, to_msisdn, media_id, text
            )
        else:
            eprint(f"✗ Upload failed with status {status}")
            eprint(f"Error response: {json.dumps(resp_json, ensure_ascii=False, indent=2)}")
    else:
        # Send text message
        assert text is not None  # For type checker
        eprint(f"Sending text message...")
        status, resp_json = send_text_message(token, phone_number_id, to_msisdn, text)

    # Print results to stdout
    print(status)
    print(json.dumps(resp_json, ensure_ascii=False, indent=2))

    # Print clear success/failure indicator to stderr
    if 200 <= status < 300:
        eprint("\n" + "=" * 60)
        eprint("✓ SUCCESS: Message sent successfully!")
        if "messages" in resp_json and resp_json["messages"]:
            msg_id = resp_json["messages"][0].get("id", "unknown")
            eprint(f"Message ID: {msg_id}")
        eprint("=" * 60)

        # Log outgoing message to daily log file
        log_event("outgoing_message", {
            "to": to_msisdn,
            "text": text or "",
            "message_type": "image" if image else "text",
            "status": status,
            "response": resp_json
        })

        return 0
    else:
        eprint("\n" + "=" * 60)
        eprint("✗ FAILED: Message sending failed!")
        eprint(f"Status code: {status}")
        if "error" in resp_json:
            error_msg = resp_json["error"].get("message", "Unknown error")
            error_code = resp_json["error"].get("code", "N/A")
            eprint(f"Error code: {error_code}")
            eprint(f"Error message: {error_msg}")
        eprint("=" * 60)
        return 1


if __name__ == "__main__":
    # Example: Send image with caption
    # main(
    #     to="972525974655",
    #     text="זה חיליק",
    #     image="data/hilik.png",
    # )

    # Use defopt for command-line argument parsing
    defopt.run(main)
