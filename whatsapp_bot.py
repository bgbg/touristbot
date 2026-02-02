#!/usr/bin/env python3
"""
WhatsApp Bot - Integrated webhook listener + RAG + sender.

Receives WhatsApp messages via webhook, processes them through the tourism
backend API, and sends responses back.

Env vars expected:
  WHATSAPP_VERIFY_TOKEN - Token for webhook verification
  BORIS_GORELIK_WABA_ACCESS_TOKEN - WhatsApp API access token
  BORIS_GORELIK_WABA_PHONE_NUMBER_ID - WhatsApp phone number ID
  BACKEND_API_URL - Backend API base URL
  BACKEND_API_KEY - Backend API authentication key

Usage:
  python whatsapp_bot.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify

load_dotenv()

app = Flask(__name__)

# Configuration
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "your-verify-token-here")
WABA_ACCESS_TOKEN = os.getenv("BORIS_GORELIK_WABA_ACCESS_TOKEN")
WABA_PHONE_NUMBER_ID = os.getenv("BORIS_GORELIK_WABA_PHONE_NUMBER_ID")
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "https://tourism-rag-backend-347968285860.me-west1.run.app")
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY")
GRAPH_API_VERSION = os.getenv("META_GRAPH_API_VERSION", "v22.0")
PORT = int(os.getenv("PORT", "8080"))

# Default location context
DEFAULT_AREA = "hefer_valley"
DEFAULT_SITE = "agamon_hefer"

# Directories
LOG_DIR = Path("whatsapp_logs")
CONV_DIR = Path("conversations")
LOG_DIR.mkdir(exist_ok=True)
CONV_DIR.mkdir(exist_ok=True)


def eprint(*args: object) -> None:
    """Print to stderr."""
    print(*args, file=sys.stderr)


def log_event(event_type: str, data: dict, correlation_id: str = None) -> None:
    """Log event to daily JSONL file."""
    timestamp = datetime.now(timezone.utc).isoformat()
    log_entry = {
        "timestamp": timestamp,
        "event_type": event_type,
        "correlation_id": correlation_id,
        "data": data,
    }

    # Log to daily file
    log_file = LOG_DIR / f"{datetime.now(timezone.utc).date()}.jsonl"
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        eprint(f"[ERROR] Failed to write log: {e}")

    # Also print to console
    eprint(f"[{timestamp}] {event_type}")
    if event_type == "error":
        eprint(json.dumps(data, ensure_ascii=False, indent=2))


def normalize_phone(raw: str) -> str:
    """Normalize phone number to digits only."""
    s = raw.strip()
    if s.startswith("+"):
        s = s[1:]
    for ch in (" ", "-", "(", ")", "."):
        s = s.replace(ch, "")
    if not s.isdigit():
        raise ValueError(f"Invalid phone number: {raw}")
    return s


def get_conversation_path(phone: str) -> Path:
    """Get path to conversation JSON file."""
    normalized = normalize_phone(phone)
    return CONV_DIR / f"whatsapp_{normalized}.json"


def load_conversation(phone: str) -> dict:
    """Load conversation from local JSON file."""
    conv_path = get_conversation_path(phone)
    if conv_path.exists():
        try:
            with open(conv_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            eprint(f"[WARNING] Failed to load conversation for {phone}: {e}")
            return create_new_conversation(phone)
    else:
        return create_new_conversation(phone)


def create_new_conversation(phone: str) -> dict:
    """Create new conversation structure."""
    normalized = normalize_phone(phone)
    return {
        "conversation_id": f"whatsapp_{normalized}",
        "phone": normalized,  # Store normalized phone for consistency
        "area": DEFAULT_AREA,
        "site": DEFAULT_SITE,
        "history": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def save_conversation(conv: dict) -> None:
    """Save conversation to local JSON file.

    Note: Local storage is for Phase 1 development/debugging only.
    Backend maintains authoritative conversation state in GCS.
    Local and backend histories may diverge on errors - this is acceptable for Phase 1.
    """
    conv["updated_at"] = datetime.now(timezone.utc).isoformat()
    conv_path = get_conversation_path(conv["phone"])
    try:
        with open(conv_path, "w", encoding="utf-8") as f:
            json.dump(conv, f, ensure_ascii=False, indent=2)
    except Exception as e:
        eprint(f"[ERROR] Failed to save conversation: {e}")


def add_interaction(conv: dict, role: str, content: str) -> None:
    """Add interaction to conversation history."""
    conv["history"].append({
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


def send_text_message(to_phone: str, text: str, correlation_id: str = None) -> tuple[int, dict]:
    """Send text message via WhatsApp API with retry logic."""
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{WABA_PHONE_NUMBER_ID}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "to": normalize_phone(to_phone),
        "type": "text",
        "text": {"body": text[:4096]},  # WhatsApp 4096 char limit
    }

    # Exponential backoff: 3 attempts with 1s, 2s, 4s delays
    for attempt in range(3):
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url=url,
                data=data,
                method="POST",
                headers={
                    "Authorization": f"Bearer {WABA_ACCESS_TOKEN}",
                    "Content-Type": "application/json",
                },
            )

            with urllib.request.urlopen(req, timeout=30) as resp:
                status = resp.getcode()
                body = resp.read().decode("utf-8", errors="replace")
                response = json.loads(body) if body else {}

                log_event("outgoing_message", {
                    "to": to_phone,
                    "text": text[:100],
                    "status": status,
                    "response": response,
                }, correlation_id)

                return status, response

        except urllib.error.HTTPError as e:
            status = e.code
            body = e.read().decode("utf-8", errors="replace")
            try:
                response = json.loads(body) if body else {"error": {"message": "Empty error body"}}
            except json.JSONDecodeError:
                response = {"error": {"message": body}}

            if attempt < 2:  # Retry on failure
                delay = 2 ** attempt  # 1s, 2s, 4s
                eprint(f"[RETRY] Attempt {attempt + 1} failed with {status}, retrying in {delay}s...")
                time.sleep(delay)
            else:
                log_event("error", {
                    "type": "whatsapp_send_failure",
                    "to": to_phone,
                    "status": status,
                    "response": response,
                    "attempts": 3,
                }, correlation_id)
                return status, response

        except Exception as e:
            if attempt < 2:
                delay = 2 ** attempt
                eprint(f"[RETRY] Attempt {attempt + 1} failed with {type(e).__name__}: {e}, retrying in {delay}s...")
                time.sleep(delay)
            else:
                log_event("error", {
                    "type": "whatsapp_send_exception",
                    "to": to_phone,
                    "error": str(e),
                    "attempts": 3,
                }, correlation_id)
                return 0, {"error": {"message": f"{type(e).__name__}: {e}"}}

    # Should never reach here
    return 0, {"error": {"message": "Max retries exceeded"}}


def call_backend_qa(conversation_id: str, area: str, site: str, query: str, correlation_id: str = None) -> dict:
    """Call backend /qa endpoint with retry logic."""
    url = f"{BACKEND_API_URL}/qa"
    headers = {
        "Authorization": f"Bearer {BACKEND_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "conversation_id": conversation_id,
        "area": area,
        "site": site,
        "query": query,
    }

    start_time = time.time()

    # Exponential backoff: 3 attempts with 1s, 2s, 4s delays
    for attempt in range(3):
        try:
            log_event("backend_request", {
                "conversation_id": conversation_id,
                "area": area,
                "site": site,
                "query": query[:100],
                "attempt": attempt + 1,
            }, correlation_id)

            response = requests.post(url, json=payload, headers=headers, timeout=60)
            latency_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                result = response.json()
                log_event("backend_response", {
                    "conversation_id": conversation_id,
                    "status": 200,
                    "latency_ms": latency_ms,
                    "response_length": len(result.get("response_text", "")),
                    "citations_count": len(result.get("citations", [])),
                    "images_count": len(result.get("images", [])),
                }, correlation_id)
                return result
            else:
                if attempt < 2 and response.status_code >= 500:  # Retry on 5xx
                    delay = 2 ** attempt
                    eprint(f"[RETRY] Backend returned {response.status_code}, retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    log_event("error", {
                        "type": "backend_error",
                        "status": response.status_code,
                        "response": response.text[:500],
                        "latency_ms": latency_ms,
                    }, correlation_id)
                    return {
                        "error": f"Backend error: {response.status_code}",
                        "response_text": "מצטער, אירעה שגיאה בשרת. אנא נסה שוב מאוחר יותר.",
                    }

        except requests.exceptions.Timeout:
            if attempt < 2:
                delay = 2 ** attempt
                eprint(f"[RETRY] Backend timeout, retrying in {delay}s...")
                time.sleep(delay)
            else:
                log_event("error", {
                    "type": "backend_timeout",
                    "latency_ms": (time.time() - start_time) * 1000,
                }, correlation_id)
                return {
                    "error": "Backend timeout",
                    "response_text": "מצטער, השרת לא הגיב בזמן. אנא נסה שוב.",
                }

        except Exception as e:
            if attempt < 2:
                delay = 2 ** attempt
                eprint(f"[RETRY] Backend call failed with {type(e).__name__}: {e}, retrying in {delay}s...")
                time.sleep(delay)
            else:
                log_event("error", {
                    "type": "backend_exception",
                    "error": str(e),
                    "traceback": traceback.format_exc()[:500],
                }, correlation_id)
                return {
                    "error": str(e),
                    "response_text": "מצטער, אירעה שגיאה. אנא נסה שוב.",
                }

    # Should never reach here
    return {
        "error": "Max retries exceeded",
        "response_text": "מצטער, אירעה שגיאה. אנא נסה שוב.",
    }


def handle_text_message(phone: str, text: str, correlation_id: str) -> None:
    """Process incoming text message and send response."""
    eprint(f"\n📱 Processing message from {phone}: {text[:50]}...")

    # Load conversation
    conv = load_conversation(phone)

    # Check for special commands
    if text.lower() in ("reset", "התחל מחדש"):
        conv["history"] = []
        save_conversation(conv)
        send_text_message(phone, "השיחה אופסה. אפשר להתחיל מחדש!", correlation_id)
        eprint("✓ Conversation reset")
        return

    # TODO: Handle location switch command (future)
    # if text.lower().startswith("switch to") or text.startswith("עבור ל"):
    #     ...

    # Add user message to history
    add_interaction(conv, "user", text)

    # Call backend API
    backend_response = call_backend_qa(
        conversation_id=conv["conversation_id"],
        area=conv["area"],
        site=conv["site"],
        query=text,
        correlation_id=correlation_id
    )

    response_text = backend_response.get("response_text", "מצטער, לא הצלחתי להבין את השאלה.")

    # Add assistant response to history
    add_interaction(conv, "assistant", response_text)

    # Save conversation
    save_conversation(conv)

    # Send response
    status, send_response = send_text_message(phone, response_text, correlation_id)

    if status < 200 or status >= 300:
        # Send failed, try fallback error message
        eprint(f"[ERROR] Failed to send response, status: {status}")
        send_text_message(phone, "מצטער, לא הצלחתי לשלוח את התשובה. אנא נסה שוב.", correlation_id)
    else:
        eprint(f"✓ Response sent successfully")


@app.route("/webhook", methods=["GET"])
def webhook_verification():
    """Webhook verification endpoint."""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    eprint(f"[VERIFICATION] mode={mode}, token={token}")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        eprint(f"[VERIFICATION] Success! Returning challenge: {challenge}")
        return challenge, 200
    else:
        eprint("[VERIFICATION] Failed! Invalid token or mode")
        return "Forbidden", 403


@app.route("/webhook", methods=["POST"])
def webhook_handler():
    """Webhook handler for incoming messages and status updates."""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"status": "error", "message": "No data"}), 400

        # Generate correlation ID for this webhook
        correlation_id = str(uuid.uuid4())

        # Log the raw webhook
        log_event("incoming_webhook", data, correlation_id)

        # Process webhook entries
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})

                # Process messages
                if "messages" in value:
                    for message in value["messages"]:
                        msg_type = message.get("type")
                        msg_from = message.get("from")

                        log_event("incoming_message", {
                            "from": msg_from,
                            "type": msg_type,
                            "message_id": message.get("id"),
                        }, correlation_id)

                        if msg_type == "text":
                            text_body = message.get("text", {}).get("body")
                            handle_text_message(msg_from, text_body, correlation_id)
                        else:
                            # Unsupported message type
                            eprint(f"\n📱 Unsupported message type: {msg_type} from {msg_from}")
                            send_text_message(
                                msg_from,
                                "מצטער, אני תומך רק בהודעות טקסט כרגע.",
                                correlation_id
                            )

                # Process status updates (sent, delivered, read, failed)
                if "statuses" in value:
                    for status in value["statuses"]:
                        status_info = {
                            "message_id": status.get("id"),
                            "status": status.get("status"),
                            "timestamp": status.get("timestamp"),
                            "recipient_id": status.get("recipient_id"),
                        }
                        log_event("status_update", status_info, correlation_id)

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        correlation_id = str(uuid.uuid4())
        eprint(f"[ERROR] {type(e).__name__}: {e}")
        log_event("error", {
            "type": "webhook_handler_exception",
            "error": str(e),
            "traceback": traceback.format_exc(),
        }, correlation_id)
        # Still return 200 to avoid WhatsApp retries
        return jsonify({"status": "error", "message": str(e)}), 200


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}), 200


if __name__ == "__main__":
    # Validate critical environment variables
    required_env_vars = {
        "BORIS_GORELIK_WABA_ACCESS_TOKEN": WABA_ACCESS_TOKEN,
        "BORIS_GORELIK_WABA_PHONE_NUMBER_ID": WABA_PHONE_NUMBER_ID,
        "BACKEND_API_KEY": BACKEND_API_KEY,
    }

    missing_vars = [name for name, value in required_env_vars.items() if not value]

    if missing_vars:
        eprint("=" * 60)
        eprint("ERROR: Missing required environment variables")
        eprint("=" * 60)
        for var in missing_vars:
            eprint(f"  - {var}")
        eprint("\nPlease set these variables in your .env file or environment.")
        eprint("See WHATSAPP_WEBHOOK_README.md for setup instructions.")
        eprint("=" * 60)
        sys.exit(1)

    eprint("=" * 60)
    eprint("WhatsApp Bot - Tourism RAG Integration")
    eprint("=" * 60)
    eprint(f"Port: {PORT}")
    eprint(f"Verify Token: {VERIFY_TOKEN}")
    eprint(f"Backend API: {BACKEND_API_URL}")
    eprint(f"Log Directory: {LOG_DIR.absolute()}")
    eprint(f"Conversations Directory: {CONV_DIR.absolute()}")
    eprint(f"Default Location: {DEFAULT_AREA}/{DEFAULT_SITE}")
    eprint("\nTo expose this server with ngrok:")
    eprint(f"  ngrok http {PORT}")
    eprint("\nThen configure the webhook URL in Meta Developer Console:")
    eprint(f"  <ngrok-url>/webhook")
    eprint("=" * 60)

    # Run Flask app
    debug_mode = os.getenv("FLASK_DEBUG", "").lower() in ("1", "true", "yes", "on")
    app.run(host="0.0.0.0", port=PORT, debug=debug_mode)
