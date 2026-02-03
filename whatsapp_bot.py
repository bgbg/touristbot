#!/usr/bin/env python3
"""
WhatsApp Bot - Integrated webhook listener + RAG + sender.

Receives WhatsApp messages via webhook, processes them through the tourism
backend API, and sends responses back.

Env vars expected:
  WHATSAPP_VERIFY_TOKEN - Token for webhook verification
  WHATSAPP_ACCESS_TOKEN - WhatsApp API access token
  WHATSAPP_PHONE_NUMBER_ID - WhatsApp phone number ID
  BACKEND_API_URL - Backend API base URL
  BACKEND_API_KEY - Backend API authentication key

Usage:
  python whatsapp_bot.py
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import tempfile
import time
import traceback
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests
import subprocess
from dotenv import load_dotenv
from flask import Flask, request, jsonify

# Import WhatsApp utility functions for image sending and typing indicator
from whatsapp_utils import upload_media, send_image_message, send_typing_indicator

# Import GCS storage backend for conversation persistence
from backend.conversation_storage.conversations import ConversationStore
from backend.gcs_storage import GCSStorage

load_dotenv()

# Initialize GCS storage backend for conversation persistence
# Uses Application Default Credentials (ADC) - no explicit credentials needed
GCS_BUCKET = os.getenv("GCS_BUCKET")
try:
    gcs_storage = GCSStorage(GCS_BUCKET, credentials_json=None)  # None enables ADC
    conversation_store = ConversationStore(gcs_storage)
except Exception as e:
    # Fail-fast if GCS initialization fails
    print(f"[ERROR] Failed to initialize GCS storage: {e}", file=sys.stderr)
    print("[ERROR] Ensure GCS_BUCKET is set and ADC is configured", file=sys.stderr)
    raise

app = Flask(__name__)

# Configuration
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "your-verify-token-here")
WABA_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
WABA_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
# Auto-detect environment: use local backend in dev, Cloud Run backend in production
# Can be overridden by setting USE_LOCAL_BACKEND explicitly in .env
USE_LOCAL_BACKEND = os.getenv("USE_LOCAL_BACKEND", "false" if os.getenv("K_SERVICE") else "true").lower() in ("true", "1", "yes")
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8001"))
BACKEND_API_URL = os.getenv("BACKEND_API_URL",
    f"http://localhost:{BACKEND_PORT}" if USE_LOCAL_BACKEND
    else "https://tourism-rag-backend-347968285860.me-west1.run.app")
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY")
GRAPH_API_VERSION = os.getenv("META_GRAPH_API_VERSION", "v22.0")
# Backward compatible PORT handling: Cloud Run uses PORT, local dev may use WHATSAPP_LISTENER_PORT
_port_env = os.getenv("PORT") or os.getenv("WHATSAPP_LISTENER_PORT")
PORT = int(_port_env) if _port_env else 8080
APP_SECRET = os.getenv("WHATSAPP_APP_SECRET")  # Optional: for signature validation

# Backend process (will be started if USE_LOCAL_BACKEND=true)
backend_process = None

# Default location context (Hebrew names)
DEFAULT_AREA = "עמק חפר"
DEFAULT_SITE = "אגמון חפר"

# Directories
LOG_DIR = Path("whatsapp_logs")
LOG_DIR.mkdir(exist_ok=True)

# Environment validation (runs at module import, before gunicorn starts serving)
def _validate_required_env_vars() -> None:
    """Validate required environment variables at startup (fail fast)."""
    required_vars = {
        "WHATSAPP_VERIFY_TOKEN": "Token for Meta webhook verification",
        "WHATSAPP_ACCESS_TOKEN": "WhatsApp Business API access token",
        "WHATSAPP_PHONE_NUMBER_ID": "WhatsApp phone number ID",
        "BACKEND_API_KEY": "Backend API authentication key",
        "GCS_BUCKET": "Google Cloud Storage bucket for conversation persistence (use Application Default Credentials for auth)",
    }

    # In production, WHATSAPP_APP_SECRET is also required for webhook signature validation
    is_production = os.getenv("K_SERVICE") or os.getenv("GAE_ENV")
    if is_production:
        required_vars["WHATSAPP_APP_SECRET"] = "Meta app secret for webhook signature validation (required in production)"

    missing_vars = []
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing_vars.append(f"  - {var}: {description}")

    if missing_vars:
        error_msg = "Missing required environment variables:\n" + "\n".join(missing_vars)
        print(error_msg, file=sys.stderr)
        raise RuntimeError(error_msg)

# Run validation at module import time (before gunicorn starts serving requests)
_validate_required_env_vars()


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


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """
    Verify Meta webhook signature using HMAC-SHA256.

    Args:
        payload: Raw request body bytes
        signature: X-Hub-Signature-256 header value (format: "sha256=<hex>")

    Returns:
        True if signature is valid, False otherwise
    """
    # Detect production environment (Cloud Run sets K_SERVICE, App Engine sets GAE_ENV)
    is_production = os.getenv("K_SERVICE") or os.getenv("GAE_ENV")

    if not APP_SECRET:
        if is_production:
            # Production: Fail closed - reject all requests without app secret
            eprint("[SECURITY] WHATSAPP_APP_SECRET not set in production - rejecting request")
            return False
        else:
            # Local dev: Warn but allow (for testing without Meta app secret)
            eprint("[WARNING] WHATSAPP_APP_SECRET not set - skipping signature validation (local dev mode)")
            return True

    if not signature or not signature.startswith("sha256="):
        return False

    # Extract hex signature from header
    expected_signature = signature[7:]  # Remove "sha256=" prefix

    # Compute HMAC-SHA256 signature
    mac = hmac.new(APP_SECRET.encode(), msg=payload, digestmod=hashlib.sha256)
    computed_signature = mac.hexdigest()

    # Constant-time comparison to prevent timing attacks
    return hmac.compare_digest(computed_signature, expected_signature)


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


def download_image_from_url(url: str) -> bytes:
    """
    Download image from URL (GCS signed URL).

    Args:
        url: Image URL to download (GCS signed URL from backend)

    Returns:
        Raw image bytes

    Raises:
        Exception: On download failure (timeout, 404, network error)
    """
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.getcode() != 200:
            raise Exception(f"Download failed with status {resp.getcode()}")
        return resp.read()


def load_conversation(phone: str):
    """Load conversation from GCS or create new one."""
    normalized = normalize_phone(phone)
    conversation_id = f"whatsapp_{normalized}"

    try:
        # Try to load existing conversation from GCS
        conv = conversation_store.get_conversation(conversation_id)
        if conv:
            # Check if all messages were expired (conversation exists but empty after filtering)
            if len(conv.messages) == 0:
                eprint(f"[CONV] Loaded conversation with all messages expired: {conversation_id}")
                eprint(f"[CONV] Starting fresh conversation after expiration")
            else:
                eprint(f"[CONV] Loaded existing conversation: {conversation_id} ({len(conv.messages)} messages)")
            return conv
        else:
            # Create new conversation
            eprint(f"[CONV] Creating new conversation: {conversation_id}")
            conv = conversation_store.create_conversation(
                area=DEFAULT_AREA,
                site=DEFAULT_SITE,
                conversation_id=conversation_id
            )
            # Save immediately to GCS
            conversation_store.save_conversation(conv)
            return conv
    except Exception as e:
        eprint(f"[ERROR] Failed to load/create conversation: {e}")
        # Fail-fast: re-raise exception to trigger error response
        raise


# Removed: add_interaction() - replaced by ConversationStore.add_message()


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


def send_image_with_retry(to_phone: str, image_url: str, caption: str, correlation_id: str = None) -> tuple[int, dict]:
    """
    Send image to WhatsApp with retry logic.

    Downloads image from URL, uploads to WhatsApp, and sends with caption.
    Uses exponential backoff retry (3 attempts: 1s, 2s, 4s delays).

    Args:
        to_phone: Recipient phone number
        image_url: GCS signed URL to download image from
        caption: Image caption (will be truncated to 1024 chars)
        correlation_id: Request correlation ID for logging

    Returns:
        Tuple of (status_code, response_dict)
    """
    normalized_phone = normalize_phone(to_phone)

    # Exponential backoff: 3 attempts with 1s, 2s, 4s delays
    for attempt in range(3):
        temp_file = None
        try:
            # Download image
            eprint(f"[IMAGE] Downloading from {image_url[:50]}...")
            image_bytes = download_image_from_url(image_url)

            # Check size (WhatsApp 5MB limit)
            size_mb = len(image_bytes) / (1024 * 1024)
            if size_mb > 5:
                eprint(f"[WARNING] Image too large: {size_mb:.2f}MB > 5MB limit")
                log_event("error", {
                    "type": "image_too_large",
                    "to": to_phone,
                    "image_url": image_url[:100],
                    "size_mb": size_mb,
                }, correlation_id)
                return 0, {"error": {"message": f"Image too large: {size_mb:.2f}MB"}}

            # Detect image format from magic numbers
            import imghdr
            image_format = imghdr.what(None, h=image_bytes[:32])
            suffix = f'.{image_format}' if image_format else '.jpg'  # Default to .jpg if detection fails

            # Save to temp file with correct extension
            with tempfile.NamedTemporaryFile(mode='wb', suffix=suffix, delete=False) as f:
                f.write(image_bytes)
                temp_file = f.name

            eprint(f"[IMAGE] Uploading to WhatsApp ({size_mb:.2f}MB)...")

            # Upload to WhatsApp
            status, upload_response = upload_media(
                WABA_ACCESS_TOKEN,
                WABA_PHONE_NUMBER_ID,
                temp_file
            )

            if status < 200 or status >= 300 or "id" not in upload_response:
                eprint(f"[ERROR] Upload failed: status={status}, response={upload_response}")
                if attempt < 2:
                    delay = 2 ** attempt
                    eprint(f"[RETRY] Attempt {attempt + 1} failed, retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    log_event("error", {
                        "type": "image_upload_failure",
                        "to": to_phone,
                        "image_url": image_url[:100],
                        "status": status,
                        "response": upload_response,
                        "attempts": 3,
                    }, correlation_id)
                    return status, upload_response

            media_id = upload_response["id"]
            eprint(f"[IMAGE] Upload successful, media_id={media_id}")

            # Send image message
            eprint(f"[IMAGE] Sending image with caption...")
            status, send_response = send_image_message(
                WABA_ACCESS_TOKEN,
                WABA_PHONE_NUMBER_ID,
                normalized_phone,
                media_id,
                caption[:1024]  # Truncate to WhatsApp limit
            )

            if 200 <= status < 300:
                eprint(f"✓ Image sent successfully")
                log_event("outgoing_image", {
                    "to": to_phone,
                    "image_url": image_url[:100],
                    "caption": caption[:100],
                    "size_mb": size_mb,
                    "media_id": media_id,
                    "status": status,
                }, correlation_id)
                return status, send_response
            else:
                eprint(f"[ERROR] Send failed: status={status}, response={send_response}")
                if attempt < 2:
                    delay = 2 ** attempt
                    eprint(f"[RETRY] Attempt {attempt + 1} failed, retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    log_event("error", {
                        "type": "image_send_failure",
                        "to": to_phone,
                        "image_url": image_url[:100],
                        "status": status,
                        "response": send_response,
                        "attempts": 3,
                    }, correlation_id)
                    return status, send_response

        except Exception as e:
            eprint(f"[ERROR] Image send exception: {type(e).__name__}: {e}")
            if attempt < 2:
                delay = 2 ** attempt
                eprint(f"[RETRY] Attempt {attempt + 1} failed, retrying in {delay}s...")
                time.sleep(delay)
            else:
                log_event("error", {
                    "type": "image_send_exception",
                    "to": to_phone,
                    "image_url": image_url[:100],
                    "error": str(e),
                    "attempts": 3,
                }, correlation_id)
                return 0, {"error": {"message": f"{type(e).__name__}: {e}"}}
        finally:
            # Clean up temp file
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except Exception as e:
                    eprint(f"[WARNING] Failed to delete temp file {temp_file}: {e}")

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
    try:
        conv = load_conversation(phone)
    except Exception as e:
        eprint(f"[ERROR] Failed to load conversation: {e}")
        send_text_message(phone, "מצטער, אירעה שגיאה בטעינת השיחה. אנא נסה שוב מאוחר יותר.", correlation_id)
        return

    # Check for special commands
    if text.lower() in ("reset", "התחל מחדש"):
        # Clear conversation history by recreating conversation
        normalized = normalize_phone(phone)
        conversation_id = f"whatsapp_{normalized}"
        try:
            # Delete old conversation and create new one
            conversation_store.delete_conversation(conversation_id)
            conv = conversation_store.create_conversation(
                area=DEFAULT_AREA,
                site=DEFAULT_SITE,
                conversation_id=conversation_id
            )
            conversation_store.save_conversation(conv)
            send_text_message(phone, "השיחה אופסה. אפשר להתחיל מחדש!", correlation_id)
            eprint("✓ Conversation reset")
            return
        except Exception as e:
            eprint(f"[ERROR] Failed to reset conversation: {e}")
            send_text_message(phone, "מצטער, לא הצלחתי לאפס את השיחה. אנא נסה שוב.", correlation_id)
            return

    # TODO: Handle location switch command (future)
    # if text.lower().startswith("switch to") or text.startswith("עבור ל"):
    #     ...

    # Add user message to history (automatically saves to GCS)
    try:
        conversation_store.add_message(conv, "user", text)
    except Exception as e:
        eprint(f"[ERROR] Failed to save user message: {e}")
        send_text_message(phone, "מצטער, אירעה שגיאה בשמירת ההודעה. אנא נסה שוב.", correlation_id)
        return

    # Send typing indicator to show bot is processing (fire-and-forget, non-blocking)
    try:
        status, resp = send_typing_indicator(WABA_ACCESS_TOKEN, WABA_PHONE_NUMBER_ID, normalize_phone(phone))
        if status == 200:
            eprint("[TYPING] Typing indicator sent")
        else:
            eprint(f"[WARNING] Typing indicator returned status {status}: {resp}")
    except Exception as e:
        # Never block message processing on typing indicator failure
        eprint(f"[WARNING] Failed to send typing indicator: {e}")

    # Call backend API
    backend_response = call_backend_qa(
        conversation_id=conv.conversation_id,
        area=conv.area,
        site=conv.site,
        query=text,
        correlation_id=correlation_id
    )

    response_text = backend_response.get("response_text", "מצטער, לא הצלחתי להבין את השאלה.")

    # Defensive type validation for response_text (follow pattern from PR #58)
    if not isinstance(response_text, str):
        eprint(f"[ERROR] response_text is not a string! Type: {type(response_text)}. Converting to string.")
        log_event("error", {
            "type": "invalid_response_text_type",
            "actual_type": str(type(response_text)),
            "value": str(response_text)[:200],
        }, correlation_id)
        response_text = str(response_text)

    # Check if images should be sent
    should_include_images = backend_response.get("should_include_images", False)
    images = backend_response.get("images", [])

    # Defensive validation for images field
    if not isinstance(images, list):
        eprint(f"[WARNING] images field is not a list! Type: {type(images)}. Ignoring images.")
        log_event("error", {
            "type": "invalid_images_type",
            "actual_type": str(type(images)),
        }, correlation_id)
        images = []

    # Send image if available and should be included
    if should_include_images and images:
        # Send only the first image (backend sorted by relevance)
        first_image = images[0]

        # Defensive validation: ensure first_image is a dictionary
        if not isinstance(first_image, dict):
            eprint(f"[WARNING] First image entry is not a dict! Type: {type(first_image)}. Skipping image send.")
            log_event("error", {
                "type": "invalid_image_entry_type",
                "actual_type": str(type(first_image)),
            }, correlation_id)
        else:
            image_url = first_image.get("uri")  # GCS signed URL
            caption_raw = first_image.get("caption", "")

            # Defensive validation: ensure caption is a string
            if not isinstance(caption_raw, str):
                eprint(f"[WARNING] Caption field is not a string! Type: {type(caption_raw)}. Using empty caption.")
                log_event("error", {
                    "type": "invalid_caption_type",
                    "actual_type": str(type(caption_raw)),
                }, correlation_id)
                caption = ""
            else:
                caption = caption_raw

            if image_url:
                eprint(f"[IMAGE] Sending image: {caption[:50]}...")
                image_status, image_response = send_image_with_retry(
                    phone,
                    image_url,
                    caption,
                    correlation_id
                )

                if image_status < 200 or image_status >= 300:
                    eprint(f"[WARNING] Image send failed, continuing with text response")
                    # Don't block text response if image fails
            else:
                eprint(f"[WARNING] Image has no URI, skipping image send")

    # Add assistant response to history with images (automatically saves to GCS)
    # This is CRITICAL for duplicate prevention - must save images that were sent
    try:
        conversation_store.add_message(
            conv,
            "assistant",
            response_text,
            citations=backend_response.get("citations", []),
            images=images if (should_include_images and images) else []
        )
    except Exception as e:
        eprint(f"[ERROR] Failed to save assistant message: {e}")
        # Continue anyway - send response to user even if save fails

    # Send text response
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
        # Verify webhook signature (Meta X-Hub-Signature-256)
        signature = request.headers.get("X-Hub-Signature-256", "")
        payload = request.get_data()

        if not verify_webhook_signature(payload, signature):
            eprint("[SECURITY] Invalid webhook signature - rejecting request")
            log_event("error", {
                "type": "invalid_webhook_signature",
                "signature": signature[:20] + "..." if len(signature) > 20 else signature,
                "ip": request.remote_addr,
            })
            return jsonify({"status": "error", "message": "Invalid signature"}), 403

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
        "WHATSAPP_ACCESS_TOKEN": WABA_ACCESS_TOKEN,
        "WHATSAPP_PHONE_NUMBER_ID": WABA_PHONE_NUMBER_ID,
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
    eprint(f"GCS Bucket: {GCS_BUCKET} (using ADC for authentication)")
    eprint(f"Default Location: {DEFAULT_AREA}/{DEFAULT_SITE}")
    eprint("=" * 60)

    # Only run startup logic once (not in Flask reloader child process)
    # This prevents backend and ngrok from restarting on every code change
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        # Start local backend if USE_LOCAL_BACKEND=true
        if USE_LOCAL_BACKEND:
            try:
                # Kill any existing process on backend port
                eprint(f"\n🔍 Checking for processes on port {BACKEND_PORT}...")
                try:
                    result = subprocess.run(
                        ["lsof", "-ti", f":{BACKEND_PORT}"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.stdout.strip():
                        pids = result.stdout.strip().split('\n')
                        for pid in pids:
                            eprint(f"   Terminating process {pid} on port {BACKEND_PORT}")
                            # Try graceful termination first (SIGTERM)
                            subprocess.run(["kill", pid], timeout=5)
                        # Wait for graceful shutdown
                        time.sleep(2)
                        # Check if any processes still running, force kill if necessary
                        result2 = subprocess.run(
                            ["lsof", "-ti", f":{BACKEND_PORT}"],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if result2.stdout.strip():
                            remaining_pids = result2.stdout.strip().split('\n')
                            for pid in remaining_pids:
                                eprint(f"   Force killing process {pid} (SIGKILL)")
                                subprocess.run(["kill", "-9", pid], timeout=5)
                            time.sleep(1)
                except Exception as e:
                    eprint(f"   (Could not check/kill processes: {e})")

                eprint(f"🚀 Starting local backend on port {BACKEND_PORT}...")
                # Pass environment variables to backend subprocess
                backend_env = os.environ.copy()
                backend_process = subprocess.Popen(
                    [sys.executable, "-m", "uvicorn", "backend.main:app",
                     "--reload", "--port", str(BACKEND_PORT), "--host", "127.0.0.1"],
                    env=backend_env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                eprint(f"✓ Backend process started (PID: {backend_process.pid})")
                eprint(f"📡 Backend API: http://localhost:{BACKEND_PORT}")

                # Wait a moment for backend to start
                time.sleep(2)
            except Exception as e:
                eprint(f"⚠️  Warning: Could not start local backend: {e}")
                eprint(f"💡 You can manually run: uvicorn backend.main:app --reload --port {BACKEND_PORT}")
                sys.exit(1)

        # Setup and start ngrok tunnel
        public_url = None
        try:
            # First, check if ngrok is already running
            # ngrok exposes a local API at http://127.0.0.1:4040/api/tunnels
            try:
                ngrok_api_response = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=2)
                if ngrok_api_response.status_code == 200:
                    tunnels_data = ngrok_api_response.json()
                    for tunnel in tunnels_data.get("tunnels", []):
                        # Look for tunnel on our port
                        config_addr = tunnel.get("config", {}).get("addr", "")
                        if f"localhost:{PORT}" in config_addr or f"127.0.0.1:{PORT}" in config_addr:
                            public_url = tunnel.get("public_url")
                            if public_url:
                                eprint(f"\n✓ Found existing ngrok tunnel")
                                break
            except Exception:
                # ngrok API not available (not running)
                pass

            # If no existing tunnel found, start ngrok as background process
            if not public_url:
                import shutil
                system_ngrok = shutil.which("ngrok")
                if not system_ngrok:
                    raise Exception("ngrok not found in PATH")

                eprint(f"\n⚡ Starting ngrok tunnel on port {PORT} (background process)...")
                # Start ngrok as detached background process
                subprocess.Popen(
                    [system_ngrok, "http", str(PORT), "--log=stdout"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True  # Detach from parent process
                )

                # Wait for ngrok to start and get the tunnel URL
                for attempt in range(10):
                    time.sleep(1)
                    try:
                        ngrok_api_response = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=2)
                        if ngrok_api_response.status_code == 200:
                            tunnels_data = ngrok_api_response.json()
                            for tunnel in tunnels_data.get("tunnels", []):
                                config_addr = tunnel.get("config", {}).get("addr", "")
                                if f"localhost:{PORT}" in config_addr or f"127.0.0.1:{PORT}" in config_addr:
                                    public_url = tunnel.get("public_url")
                                    if public_url:
                                        eprint(f"✓ ngrok tunnel started (persists across bot restarts)")
                                        break
                            if public_url:
                                break
                    except Exception:
                        # Retry on any error (network, JSON parsing, etc.)
                        # Will retry up to 10 times before raising exception below
                        continue

                if not public_url:
                    raise Exception("Failed to get ngrok tunnel URL after 10 seconds")

            if public_url:
                eprint(f"\n🌐 Local:      http://127.0.0.1:{PORT}")
                eprint(f"🌐 Public:     {public_url}")
                eprint(f"\n📋 Webhook URL for Meta Console:")
                eprint(f"   {public_url}/webhook")
                eprint("=" * 60)

        except Exception as e:
            eprint(f"\n⚠️  Warning: Could not start ngrok: {e}")
            eprint(f"💡 You can manually run: ngrok http {PORT}")
            eprint(f"🌐 Local only: http://127.0.0.1:{PORT}")
            eprint("=" * 60)

    # Run Flask app with auto-reload enabled
    # Default: debug mode OFF for security (must be explicitly enabled via FLASK_DEBUG)
    flask_debug_env = os.getenv("FLASK_DEBUG")
    if flask_debug_env is None:
        debug_mode = False
        use_reloader = False
    else:
        debug_mode = flask_debug_env.lower() in ("1", "true", "yes", "on")
        use_reloader = debug_mode

    try:
        app.run(host="0.0.0.0", port=PORT, debug=debug_mode, use_reloader=use_reloader)
    finally:
        # Clean up backend process on exit
        if backend_process and backend_process.poll() is None:
            eprint("\n🛑 Stopping local backend...")
            backend_process.terminate()
            backend_process.wait(timeout=5)
            eprint("✓ Backend stopped")
