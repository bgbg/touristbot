#!/usr/bin/env python3
"""
WhatsApp utility functions for sending messages and media via Meta WhatsApp Cloud API.

This module provides reusable functions for:
- Sending text messages
- Uploading and sending images
- Sending typing indicators (typing animation)
- Sending read receipts (blue checkmarks)
- Phone number normalization

Used by both whatsapp_bot.py and send_whatsapp_message.py.
"""

from __future__ import annotations

import json
import mimetypes
import os
import urllib.parse
import urllib.request
import uuid
from typing import Optional


GRAPH_API_VERSION = os.getenv("META_GRAPH_API_VERSION", "v22.0")


def normalize_msisdn(raw: str) -> str:
    """
    WhatsApp Cloud API expects phone numbers in international format, digits only.
    Example: 972525974655

    Args:
        raw: Phone number in any format (e.g., "+972-52-597-4655")

    Returns:
        Normalized phone number (digits only)

    Raises:
        ValueError: If phone number contains non-digit characters after cleanup
    """
    s = raw.strip()
    if s.startswith("+"):
        s = s[1:]
    # remove common separators
    for ch in (" ", "-", "(", ")", "."):
        s = s.replace(ch, "")
    if not s.isdigit():
        raise ValueError(
            f"Invalid phone number (must be digits only after cleanup): {raw!r} -> {s!r}"
        )
    return s


def upload_media(token: str, phone_number_id: str, file_path: str) -> tuple[int, dict]:
    """
    Upload a media file to WhatsApp and return the media ID.

    Args:
        token: WhatsApp access token
        phone_number_id: WhatsApp phone number ID
        file_path: Path to local file to upload

    Returns:
        Tuple of (status_code, response_dict with 'id' key on success)
    """
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_number_id}/media"

    # Determine MIME type based on file extension
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = "application/octet-stream"

    # Read file
    try:
        with open(file_path, "rb") as f:
            file_data = f.read()
    except Exception as e:
        return 0, {"error": {"message": f"Failed to read file: {e}"}}

    # Create multipart form data
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex[:16]}"

    body_parts = []

    # Add messaging_product field
    body_parts.append(f"--{boundary}\r\n")
    body_parts.append(
        'Content-Disposition: form-data; name="messaging_product"\r\n\r\n'
    )
    body_parts.append("whatsapp\r\n")

    # Add file field
    filename = os.path.basename(file_path)
    body_parts.append(f"--{boundary}\r\n")
    body_parts.append(
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
    )
    body_parts.append(f"Content-Type: {mime_type}\r\n\r\n")

    # Build body
    body = (
        "".join(body_parts).encode("utf-8")
        + file_data
        + f"\r\n--{boundary}--\r\n".encode("utf-8")
    )

    req = urllib.request.Request(
        url=url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            status = resp.getcode()
            body = resp.read().decode("utf-8", errors="replace")
            return status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        status = e.code
        body = e.read().decode("utf-8", errors="replace")
        try:
            return status, (
                json.loads(body) if body else {"error": {"message": "Empty error body"}}
            )
        except json.JSONDecodeError:
            return status, {"error": {"message": body}}
    except Exception as e:
        return 0, {"error": {"message": f"{type(e).__name__}: {e}"}}


def send_text_message(
    token: str, phone_number_id: str, to_msisdn: str, text: str
) -> tuple[int, dict]:
    """
    Send a text message via WhatsApp Cloud API.

    Args:
        token: WhatsApp access token
        phone_number_id: WhatsApp phone number ID
        to_msisdn: Recipient phone number (digits only, international format)
        text: Message text to send

    Returns:
        Tuple of (status_code, response_dict)
    """
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_number_id}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "to": to_msisdn,
        "type": "text",
        "text": {"body": text},
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.getcode()
            body = resp.read().decode("utf-8", errors="replace")
            return status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        status = e.code
        body = e.read().decode("utf-8", errors="replace")
        try:
            return status, (
                json.loads(body) if body else {"error": {"message": "Empty error body"}}
            )
        except json.JSONDecodeError:
            return status, {"error": {"message": body}}
    except Exception as e:
        return 0, {"error": {"message": f"{type(e).__name__}: {e}"}}


def send_image_message(
    token: str,
    phone_number_id: str,
    to_msisdn: str,
    media_id: str,
    caption: Optional[str] = None,
) -> tuple[int, dict]:
    """
    Send an image message using a media ID.

    Args:
        token: WhatsApp access token
        phone_number_id: WhatsApp phone number ID
        to_msisdn: Recipient phone number (digits only, international format)
        media_id: Media ID from upload_media()
        caption: Optional image caption (max 1024 chars for WhatsApp)

    Returns:
        Tuple of (status_code, response_dict)
    """
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_number_id}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "to": to_msisdn,
        "type": "image",
        "image": {"id": media_id},
    }

    if caption:
        # Truncate caption to WhatsApp limit (1024 chars)
        payload["image"]["caption"] = caption[:1024]

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.getcode()
            body = resp.read().decode("utf-8", errors="replace")
            return status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        status = e.code
        body = e.read().decode("utf-8", errors="replace")
        try:
            return status, (
                json.loads(body) if body else {"error": {"message": "Empty error body"}}
            )
        except json.JSONDecodeError:
            return status, {"error": {"message": body}}
    except Exception as e:
        return 0, {"error": {"message": f"{type(e).__name__}: {e}"}}


def send_read_receipt(
    token: str, phone_number_id: str, message_id: str, typing_indicator: bool = False
) -> tuple[int, dict]:
    """
    Mark message as read (sends blue checkmarks to sender).

    Optionally displays a typing indicator animation for up to 25 seconds.

    This is the WhatsApp read receipt API - it marks a message as read and shows
    blue checkmarks to the sender. When typing_indicator=True, it also shows
    a typing animation that lasts up to 25 seconds or until the next message.

    Args:
        token: WhatsApp access token
        phone_number_id: WhatsApp phone number ID
        message_id: Message ID from incoming webhook (required to mark as read)
        typing_indicator: If True, show typing animation (default: False)

    Returns:
        Tuple of (status_code, response_dict)

    Example:
        >>> # Just read receipt (blue checkmarks)
        >>> status, resp = send_read_receipt(token, phone_id, "wamid.XXX...")
        >>>
        >>> # Read receipt + typing indicator
        >>> status, resp = send_read_receipt(token, phone_id, "wamid.XXX...", typing_indicator=True)
        >>> if status == 200:
        ...     print("Message marked as read with typing animation")
    """
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_number_id}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }

    # Add typing indicator if requested (per official Meta documentation)
    if typing_indicator:
        payload["typing_indicator"] = {"type": "text"}

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.getcode()
            body = resp.read().decode("utf-8", errors="replace")
            return status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        status = e.code
        body = e.read().decode("utf-8", errors="replace")
        try:
            return status, (
                json.loads(body) if body else {"error": {"message": "Empty error body"}}
            )
        except json.JSONDecodeError:
            return status, {"error": {"message": body}}
    except Exception as e:
        return 0, {"error": {"message": f"{type(e).__name__}: {e}"}}


# DEPRECATED: send_typing_indicator() has been removed.
# Typing indicators are now sent together with read receipts in a single API call.
# Use send_read_receipt(token, phone_number_id, message_id, typing_indicator=True) instead.
#
# Per Meta's official documentation (updated Oct 2025):
# https://developers.facebook.com/documentation/business-messaging/whatsapp/typing-indicators/
# The typing indicator must be sent with the read receipt in the same request.
