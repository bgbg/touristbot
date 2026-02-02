#!/usr/bin/env python3
"""
WhatsApp webhook listener for receiving incoming messages.

Env vars expected:
  WHATSAPP_VERIFY_TOKEN - Token for webhook verification

Usage:
  python whatsapp_listener.py

Then expose with ngrok:
  ngrok http 5000
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, request, jsonify

load_dotenv()

app = Flask(__name__)

# Webhook verification token (set this in .env)
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "your-verify-token-here")

# Port (configurable via env var)
PORT = int(os.getenv("WHATSAPP_LISTENER_PORT", "5001"))

# Log directory
LOG_DIR = Path("whatsapp_logs")
LOG_DIR.mkdir(exist_ok=True)


def log_webhook(event_type: str, data: dict) -> None:
    """Log webhook events to file."""
    timestamp = datetime.utcnow().isoformat()
    log_entry = {
        "timestamp": timestamp,
        "event_type": event_type,
        "data": data,
    }

    # Log to daily file
    log_file = LOG_DIR / f"{datetime.utcnow().date()}.jsonl"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    # Also print to console
    print(f"[{timestamp}] {event_type}", file=sys.stderr)
    print(json.dumps(data, ensure_ascii=False, indent=2), file=sys.stderr)


def extract_message_info(message: dict) -> dict:
    """Extract useful information from a WhatsApp message."""
    info = {
        "message_id": message.get("id"),
        "from": message.get("from"),
        "timestamp": message.get("timestamp"),
        "type": message.get("type"),
    }

    # Extract message content based on type
    msg_type = message.get("type")
    if msg_type == "text":
        info["text"] = message.get("text", {}).get("body")
    elif msg_type == "image":
        img = message.get("image", {})
        info["image"] = {
            "id": img.get("id"),
            "mime_type": img.get("mime_type"),
            "caption": img.get("caption"),
        }
    elif msg_type == "audio":
        audio = message.get("audio", {})
        info["audio"] = {
            "id": audio.get("id"),
            "mime_type": audio.get("mime_type"),
        }
    elif msg_type == "video":
        video = message.get("video", {})
        info["video"] = {
            "id": video.get("id"),
            "mime_type": video.get("mime_type"),
            "caption": video.get("caption"),
        }
    elif msg_type == "document":
        doc = message.get("document", {})
        info["document"] = {
            "id": doc.get("id"),
            "filename": doc.get("filename"),
            "mime_type": doc.get("mime_type"),
        }
    elif msg_type == "location":
        loc = message.get("location", {})
        info["location"] = {
            "latitude": loc.get("latitude"),
            "longitude": loc.get("longitude"),
            "name": loc.get("name"),
            "address": loc.get("address"),
        }

    return info


@app.route("/webhook", methods=["GET"])
def webhook_verification():
    """
    Webhook verification endpoint.
    WhatsApp sends GET request with hub.mode, hub.challenge, hub.verify_token.
    """
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    print(f"[VERIFICATION] mode={mode}, token={token}", file=sys.stderr)

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print(
            f"[VERIFICATION] Success! Returning challenge: {challenge}", file=sys.stderr
        )
        return challenge, 200
    else:
        print("[VERIFICATION] Failed! Invalid token or mode", file=sys.stderr)
        return "Forbidden", 403


@app.route("/webhook", methods=["POST"])
def webhook_handler():
    """
    Webhook handler for incoming messages and status updates.
    WhatsApp sends POST request with JSON payload.
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"status": "error", "message": "No data"}), 400

        # Log the raw webhook
        log_webhook("incoming_webhook", data)

        # Process webhook entries
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})

                # Process messages
                if "messages" in value:
                    for message in value["messages"]:
                        msg_info = extract_message_info(message)
                        log_webhook("incoming_message", msg_info)

                        # Print friendly message to console
                        msg_type = msg_info.get("type")
                        sender = msg_info.get("from")
                        print(
                            f"\n📱 New {msg_type} message from {sender}",
                            file=sys.stderr,
                        )

                        if msg_type == "text":
                            print(f"   Text: {msg_info.get('text')}", file=sys.stderr)
                        elif msg_type == "image":
                            caption = msg_info.get("image", {}).get("caption")
                            print(
                                f"   Image ID: {msg_info.get('image', {}).get('id')}",
                                file=sys.stderr,
                            )
                            if caption:
                                print(f"   Caption: {caption}", file=sys.stderr)

                # Process status updates (sent, delivered, read, failed)
                if "statuses" in value:
                    for status in value["statuses"]:
                        status_info = {
                            "message_id": status.get("id"),
                            "status": status.get("status"),
                            "timestamp": status.get("timestamp"),
                            "recipient_id": status.get("recipient_id"),
                        }
                        log_webhook("status_update", status_info)

                        print(
                            f"\n📊 Status update: {status_info['status']} for message {status_info['message_id']}",
                            file=sys.stderr,
                        )

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        log_webhook("error", {"error": str(e), "type": type(e).__name__})
        # Still return 200 to avoid WhatsApp retries
        return jsonify({"status": "error", "message": str(e)}), 200


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return (
        jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat()}),
        200,
    )


@app.route("/logs", methods=["GET"])
def view_logs():
    """View recent logs (last 50 entries)."""
    try:
        # Get today's log file
        log_file = LOG_DIR / f"{datetime.utcnow().date()}.jsonl"

        if not log_file.exists():
            return jsonify({"logs": []}), 200

        # Read last 50 lines
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        recent_logs = [json.loads(line) for line in lines[-50:]]
        return jsonify({"logs": recent_logs}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    URL = "https://bae398b9af88.ngrok-free.app"
    print("=" * 60, file=sys.stderr)
    print("WhatsApp Webhook Listener", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"Port: {PORT}", file=sys.stderr)
    print(f"Verify Token: {VERIFY_TOKEN}", file=sys.stderr)
    print(f"Log Directory: {LOG_DIR.absolute()}", file=sys.stderr)
    print("\nTo expose this server with ngrok:", file=sys.stderr)
    print(f"  ngrok http {PORT}", file=sys.stderr)
    print(
        "\nThen configure the webhook URL in Meta Developer Console:", file=sys.stderr
    )
    print(f"  {URL}/webhook", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    # Run Flask app
    app.run(host="0.0.0.0", port=PORT, debug=True)
