"""
Webhook security utilities.

Provides HMAC-SHA256 signature verification for Meta webhooks.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import sys
from typing import List, Optional


def verify_webhook_signature(
    payload: bytes,
    signature: str,
    app_secret: Optional[str] = None,
    extra_secrets: Optional[List[str]] = None,
) -> bool:
    """
    Verify Meta webhook signature using HMAC-SHA256.

    Implements security best practices:
    - Production: Fail closed (reject all requests without app secret)
    - Local dev: Warn but allow (for testing without Meta app secret)
    - Constant-time comparison to prevent timing attacks

    Args:
        payload: Raw request body bytes
        signature: X-Hub-Signature-256 header value (format: "sha256=<hex>")
        app_secret: Meta app secret (default: from WHATSAPP_APP_SECRET env var)
        extra_secrets: Additional app secrets to try (for multi-app setups)

    Returns:
        True if signature is valid, False otherwise

    Example:
        payload = request.get_data()
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not verify_webhook_signature(payload, signature):
            return jsonify({"error": "Invalid signature"}), 403
    """
    # Use provided app_secret or get from environment
    if app_secret is None:
        app_secret = os.getenv("WHATSAPP_APP_SECRET")

    # Detect production environment (Cloud Run sets K_SERVICE, App Engine sets GAE_ENV)
    is_production = bool(os.getenv("K_SERVICE") or os.getenv("GAE_ENV"))

    # Collect all secrets to try (primary + extras, filtering out None/empty)
    secrets_to_try = [s for s in ([app_secret] + (extra_secrets or [])) if s]

    if not secrets_to_try:
        if is_production:
            # Production: Fail closed - reject all requests without app secret
            print(
                "[SECURITY] WHATSAPP_APP_SECRET not set in production - rejecting request",
                file=sys.stderr
            )
            return False
        else:
            # Local dev: Warn but allow (for testing without Meta app secret)
            print(
                "[WARNING] WHATSAPP_APP_SECRET not set - skipping signature validation "
                "(local dev mode)",
                file=sys.stderr
            )
            return True

    if not signature or not signature.startswith("sha256="):
        return False

    # Extract hex signature from header
    expected_signature = signature[7:]  # Remove "sha256=" prefix

    # Try each secret — valid if any matches (constant-time comparison)
    for secret in secrets_to_try:
        mac = hmac.new(secret.encode(), msg=payload, digestmod=hashlib.sha256)
        computed_signature = mac.hexdigest()
        if hmac.compare_digest(computed_signature, expected_signature):
            return True

    return False


def is_production_environment() -> bool:
    """
    Detect if running in production environment.

    Returns:
        True if running on Cloud Run or App Engine, False otherwise
    """
    return bool(os.getenv("K_SERVICE") or os.getenv("GAE_ENV"))
