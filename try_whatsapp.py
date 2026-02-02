#!/usr/bin/env python3
"""
Send a WhatsApp message via Meta WhatsApp Cloud API.

Env vars expected:
  BORIS_GORELIK_WABA_ACCESS_TOKEN
  BORIS_GORELIK_WABA_PHONE_NUMBER_ID

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
import mimetypes
import os
import sys
import urllib.parse
import urllib.request
import uuid
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


GRAPH_API_VERSION = os.getenv("META_GRAPH_API_VERSION", "v22.0")


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def normalize_msisdn(raw: str) -> str:
    """
    WhatsApp Cloud API expects phone numbers in international format, digits only.
    Example: 972525974655
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
    Returns (status_code, response_dict with 'id' key on success)
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
    filename = file_path.split("/")[-1]
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
    caption: str | None = None,
) -> tuple[int, dict]:
    """
    Send an image message using a media ID.
    """
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_number_id}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "to": to_msisdn,
        "type": "image",
        "image": {"id": media_id},
    }

    if caption:
        payload["image"]["caption"] = caption

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

    token = os.getenv("BORIS_GORELIK_WABA_ACCESS_TOKEN")
    phone_number_id = os.getenv("BORIS_GORELIK_WABA_PHONE_NUMBER_ID")

    if not token:
        eprint("Missing env var: BORIS_GORELIK_WABA_ACCESS_TOKEN")
        return 2
    if not phone_number_id:
        eprint("Missing env var: BORIS_GORELIK_WABA_PHONE_NUMBER_ID")
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
