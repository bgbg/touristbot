"""
WhatsApp Cloud API client.

Provides interface for sending messages, images, typing indicators, and read receipts
via WhatsApp Business API.
"""

from __future__ import annotations

import imghdr
import json
import os
import tempfile
import urllib.request
import urllib.error
from typing import Tuple, Dict, Any, Optional

from .logging_utils import eprint, EventLogger
from .retry import retry

# Import WhatsApp utility functions for media upload and messaging
from whatsapp_utils import upload_media, send_image_message, send_typing_indicator, send_read_receipt


class WhatsAppClient:
    """
    WhatsApp Cloud API client for sending messages and media.

    Handles text messages, images, typing indicators, read receipts, and phone
    number normalization. Uses exponential backoff retry for transient failures.
    """

    def __init__(
        self,
        access_token: str,
        phone_number_id: str,
        graph_api_version: str = "v22.0",
        logger: Optional[EventLogger] = None
    ):
        """
        Initialize WhatsApp API client.

        Args:
            access_token: WhatsApp Business API access token
            phone_number_id: WhatsApp phone number ID
            graph_api_version: Meta Graph API version (default: v22.0)
            logger: Optional event logger for request tracing
        """
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.graph_api_version = graph_api_version
        self.base_url = f"https://graph.facebook.com/{graph_api_version}/{phone_number_id}"
        self.logger = logger

    @retry(max_attempts=3, base_delay=1.0, max_delay=4.0, logger=eprint)
    def send_text_message(
        self,
        to_phone: str,
        text: str,
        correlation_id: Optional[str] = None
    ) -> Tuple[int, Dict[str, Any]]:
        """
        Send text message via WhatsApp API with retry logic.

        Uses exponential backoff retry (3 attempts: 1s, 2s, 4s delays).

        Args:
            to_phone: Recipient phone number (will be normalized)
            text: Message text (truncated to 4096 chars - WhatsApp limit)
            correlation_id: Optional correlation ID for request tracing

        Returns:
            Tuple of (status_code, response_dict)

        Raises:
            Exception: On final retry failure (after 3 attempts)

        Example:
            client = WhatsAppClient(token, phone_id)
            status, response = client.send_text_message(
                "+972501234567",
                "Hello!",
                correlation_id="uuid-123"
            )
            if status == 200:
                print(f"Message sent: {response}")
        """
        url = f"{self.base_url}/messages"
        normalized_phone = self.normalize_phone(to_phone)

        payload = {
            "messaging_product": "whatsapp",
            "to": normalized_phone,
            "type": "text",
            "text": {"body": text[:4096]},  # WhatsApp 4096 char limit
        }

        # Log outgoing message
        if self.logger:
            self.logger.log_event("outgoing_message", {
                "to_phone": normalized_phone,
                "message_type": "text",
                "text_length": len(text),
            }, correlation_id)

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url=url,
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                status = resp.getcode()
                body = resp.read().decode("utf-8", errors="replace")
                response = json.loads(body) if body else {}
                # Log success
                if self.logger:
                    self.logger.log_event("message_sent", {
                        "to_phone": normalized_phone,
                        "status_code": status,
                        "message_type": "text",
                    }, correlation_id)
                return status, response

        except urllib.error.HTTPError as e:
            status = e.code
            body = e.read().decode("utf-8", errors="replace")
            try:
                response = json.loads(body) if body else {"error": {"message": "Empty error body"}}
            except json.JSONDecodeError:
                response = {"error": {"message": body}}
            # Log error
            if self.logger:
                self.logger.log_event("message_send_error", {
                    "to_phone": normalized_phone,
                    "status_code": status,
                    "error": response.get('error', {}).get('message', 'Unknown error'),
                }, correlation_id)
            # Re-raise to trigger retry
            raise Exception(f"HTTP {status}: {response.get('error', {}).get('message', 'Unknown error')}")

    @retry(max_attempts=3, base_delay=1.0, max_delay=4.0, logger=eprint)
    def send_image(
        self,
        to_phone: str,
        image_url: str,
        caption: str,
        correlation_id: Optional[str] = None
    ) -> Tuple[int, Dict[str, Any]]:
        """
        Send image to WhatsApp with retry logic.

        Downloads image from URL, uploads to WhatsApp, and sends with caption.
        Uses exponential backoff retry (3 attempts: 1s, 2s, 4s delays).

        Args:
            to_phone: Recipient phone number (will be normalized)
            image_url: GCS signed URL to download image from
            caption: Image caption (truncated to 1024 chars - WhatsApp limit)
            correlation_id: Optional correlation ID for request tracing

        Returns:
            Tuple of (status_code, response_dict)

        Raises:
            Exception: On final retry failure or if image > 5MB

        Example:
            client = WhatsAppClient(token, phone_id)
            status, response = client.send_image(
                "+972501234567",
                "https://storage.googleapis.com/...",
                "Beautiful sunset",
                correlation_id="uuid-123"
            )
        """
        normalized_phone = self.normalize_phone(to_phone)
        temp_file: Optional[str] = None

        # Log outgoing image message
        if self.logger:
            self.logger.log_event("outgoing_message", {
                "to_phone": normalized_phone,
                "message_type": "image",
                "image_url": image_url[:100],
                "caption_length": len(caption),
            }, correlation_id)

        try:
            # Download image
            eprint(f"[IMAGE] Downloading from {image_url[:50]}...")
            image_bytes = self.download_image_from_url(image_url)

            # Check size (WhatsApp 5MB limit)
            size_mb = len(image_bytes) / (1024 * 1024)
            if size_mb > 5:
                eprint(f"[WARNING] Image too large: {size_mb:.2f}MB > 5MB limit")
                raise Exception(f"Image too large: {size_mb:.2f}MB")

            # Detect image format from magic numbers
            image_format = imghdr.what(None, h=image_bytes[:32])
            suffix = f'.{image_format}' if image_format else '.jpg'  # Default to .jpg

            # Save to temp file with correct extension
            with tempfile.NamedTemporaryFile(mode='wb', suffix=suffix, delete=False) as f:
                f.write(image_bytes)
                temp_file = f.name

            eprint(f"[IMAGE] Uploading to WhatsApp ({size_mb:.2f}MB)...")

            # Upload to WhatsApp
            status, upload_response = upload_media(
                self.access_token,
                self.phone_number_id,
                temp_file
            )

            if status < 200 or status >= 300 or "id" not in upload_response:
                eprint(f"[ERROR] Upload failed: status={status}, response={upload_response}")
                raise Exception(f"Upload failed: {upload_response.get('error', {}).get('message', 'Unknown error')}")

            media_id = upload_response["id"]
            eprint(f"[IMAGE] Upload successful, media_id={media_id}")

            # Send image message
            eprint(f"[IMAGE] Sending image with caption...")
            status, send_response = send_image_message(
                self.access_token,
                self.phone_number_id,
                normalized_phone,
                media_id,
                caption[:1024]  # Truncate to WhatsApp limit
            )

            if 200 <= status < 300:
                eprint(f"✓ Image sent successfully")
                # Log success
                if self.logger:
                    self.logger.log_event("message_sent", {
                        "to_phone": normalized_phone,
                        "status_code": status,
                        "message_type": "image",
                        "image_size_mb": size_mb,
                    }, correlation_id)
                return status, send_response
            else:
                eprint(f"[ERROR] Send failed: status={status}, response={send_response}")
                # Log error
                if self.logger:
                    self.logger.log_event("message_send_error", {
                        "to_phone": normalized_phone,
                        "status_code": status,
                        "message_type": "image",
                        "error": send_response.get('error', {}).get('message', 'Unknown error'),
                    }, correlation_id)
                raise Exception(f"Send failed: {send_response.get('error', {}).get('message', 'Unknown error')}")

        finally:
            # Clean up temp file
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except Exception as e:
                    eprint(f"[WARNING] Failed to delete temp file {temp_file}: {e}")

    def send_typing_indicator(self, to_phone: str) -> Tuple[int, Dict[str, Any]]:
        """
        Send typing indicator (typing animation).

        Shows typing animation to recipient for ~5-10 seconds. No retry logic -
        non-critical operation, failure is acceptable.

        Args:
            to_phone: Recipient phone number (will be normalized)

        Returns:
            Tuple of (status_code, response_dict)

        Example:
            client = WhatsAppClient(token, phone_id)
            status, response = client.send_typing_indicator("+972501234567")
        """
        try:
            normalized_phone = self.normalize_phone(to_phone)
            return send_typing_indicator(self.access_token, self.phone_number_id, normalized_phone)
        except Exception as e:
            eprint(f"[WARNING] Failed to send typing indicator: {e}")
            return 0, {"error": {"message": str(e)}}

    def send_read_receipt(self, message_id: str) -> Tuple[int, Dict[str, Any]]:
        """
        Mark message as read (blue checkmarks).

        Shows blue checkmarks to sender. No retry logic - non-critical operation,
        failure is acceptable.

        Args:
            message_id: WhatsApp message ID to mark as read

        Returns:
            Tuple of (status_code, response_dict)

        Example:
            client = WhatsAppClient(token, phone_id)
            status, response = client.send_read_receipt("wamid.XXX...")
        """
        try:
            return send_read_receipt(self.access_token, self.phone_number_id, message_id)
        except Exception as e:
            eprint(f"[WARNING] Failed to send read receipt: {e}")
            return 0, {"error": {"message": str(e)}}

    @staticmethod
    def normalize_phone(raw: str) -> str:
        """
        Normalize phone number to digits only.

        Removes +, spaces, hyphens, parentheses, and periods.
        Validates that result contains only digits.

        Args:
            raw: Raw phone number string

        Returns:
            Normalized phone number (digits only)

        Raises:
            ValueError: If phone number contains non-digit characters after normalization

        Example:
            normalized = WhatsAppClient.normalize_phone("+972-50-123-4567")
            # Returns: "972501234567"
        """
        s = raw.strip()
        if s.startswith("+"):
            s = s[1:]
        for ch in (" ", "-", "(", ")", "."):
            s = s.replace(ch, "")
        if not s.isdigit():
            raise ValueError(f"Invalid phone number: {raw}")
        return s

    @staticmethod
    def download_image_from_url(url: str) -> bytes:
        """
        Download image from URL (GCS signed URL).

        Args:
            url: Image URL to download (GCS signed URL from backend)

        Returns:
            Raw image bytes

        Raises:
            Exception: On download failure (timeout, 404, network error)

        Example:
            image_bytes = WhatsAppClient.download_image_from_url(
                "https://storage.googleapis.com/..."
            )
        """
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.getcode() != 200:
                raise Exception(f"Download failed with status {resp.getcode()}")
            return resp.read()
