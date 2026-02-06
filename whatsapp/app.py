"""
Flask application for WhatsApp webhook endpoints.

Provides webhook verification and message handling endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from flask import Flask, request, jsonify

from . import dependencies
from .message_handler import process_message
from .security import verify_webhook_signature
from .timing import TimingContext


def create_app() -> Flask:
    """
    Create Flask application with webhook endpoints.

    App factory pattern for easy testing and configuration.

    Returns:
        Configured Flask app

    Example:
        app = create_app()
        app.run(host="0.0.0.0", port=8080)
    """
    app = Flask(__name__)

    # Get dependencies
    config = dependencies.get_config()
    logger = dependencies.get_event_logger()
    deduplicator = dependencies.get_message_deduplicator()
    whatsapp_client = dependencies.get_whatsapp_client()
    task_manager = dependencies.get_task_manager()
    conversation_loader = dependencies.get_conversation_loader()
    backend_client = dependencies.get_backend_client()
    query_logger = dependencies.get_query_logger()
    delivery_tracker = dependencies.get_delivery_tracker()

    @app.route("/webhook", methods=["GET"])
    def webhook_verification():
        """
        Webhook verification endpoint.

        Meta will call this endpoint to verify the webhook URL during setup.
        Must return the challenge value if verify_token matches.

        Returns:
            Challenge string (200 OK) or "Forbidden" (403)
        """
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        logger.eprint(f"[VERIFICATION] mode={mode}, token={token}")

        if mode == "subscribe" and token == config.verify_token:
            logger.eprint(f"[VERIFICATION] Success! Returning challenge: {challenge}")
            return challenge, 200
        else:
            logger.eprint("[VERIFICATION] Failed! Invalid token or mode")
            return "Forbidden", 403

    @app.route("/webhook", methods=["POST"])
    def webhook_handler():
        """
        Webhook handler for incoming messages and status updates.

        Processes webhook payloads from Meta:
        - Verifies signature (HMAC-SHA256)
        - Deduplicates messages (5-minute TTL)
        - Sends typing indicator
        - Launches background thread for async processing
        - Returns 200 OK immediately (async pattern)

        Returns:
            JSON response with status (always 200 to prevent retries)
        """
        try:
            # Mark webhook received timestamp (will be copied to each message's timing context)
            webhook_received_ts = TimingContext().mark("webhook_received")

            # Verify webhook signature (Meta X-Hub-Signature-256)
            signature = request.headers.get("X-Hub-Signature-256", "")
            payload = request.get_data()

            if not verify_webhook_signature(payload, signature):
                logger.eprint("[SECURITY] Invalid webhook signature - rejecting request")
                logger.log_event("error", {
                    "type": "invalid_webhook_signature",
                    "signature": signature[:20] + "..." if len(signature) > 20 else signature,
                    "ip": request.remote_addr,
                })
                return jsonify({"status": "error", "message": "Invalid signature"}), 403

            data = request.get_json()

            if not data:
                return jsonify({"status": "error", "message": "No data"}), 400

            # Generate correlation ID for this webhook
            webhook_correlation_id = str(uuid.uuid4())

            # Log the raw webhook
            logger.log_event("incoming_webhook", data, webhook_correlation_id)

            # Process webhook entries
            for entry in data.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})

                    # Process messages
                    if "messages" in value:
                        # Extract contact profile names (keyed by wa_id)
                        contacts_map = {}
                        for contact in value.get("contacts", []):
                            wa_id = contact.get("wa_id")
                            profile_name = contact.get("profile", {}).get("name")
                            if wa_id and profile_name:
                                contacts_map[wa_id] = profile_name

                        for message in value["messages"]:
                            msg_type = message.get("type")
                            msg_from = message.get("from")
                            msg_id = message.get("id")
                            profile_name = contacts_map.get(msg_from)  # Get name for this sender

                            # Create new timing context for each message
                            # Copy webhook_received timestamp from webhook-level timing
                            msg_timing_ctx = TimingContext()
                            msg_timing_ctx.set_checkpoint("webhook_received", webhook_received_ts)

                            # Generate unique correlation ID for this message
                            correlation_id = str(uuid.uuid4())
                            msg_timing_ctx.correlation_id = correlation_id

                            logger.log_event("incoming_message", {
                                "from": msg_from,
                                "type": msg_type,
                                "message_id": msg_id,
                                "profile_name": profile_name,
                            }, correlation_id)

                            if msg_type == "text":
                                text_body = message.get("text", {}).get("body")

                                # Check for duplicate message (webhook retry)
                                if deduplicator.is_duplicate(msg_id):
                                    logger.eprint(f"[DEDUP] Ignoring duplicate message: {msg_id}")
                                    logger.log_event("message_deduplicated", {
                                        "message_id": msg_id,
                                        "from": msg_from,
                                    }, correlation_id)
                                    continue  # Skip duplicate, don't process

                                # Send read receipt with typing indicator immediately
                                # Per Meta docs: both are sent in a single API call
                                try:
                                    status, resp = whatsapp_client.send_read_receipt(msg_id, typing_indicator=True)
                                    if status == 200:
                                        logger.eprint("[READ+TYPING] Message marked as read with typing indicator")
                                    else:
                                        logger.eprint(f"[WARNING] Read receipt/typing indicator returned status {status}: {resp}")
                                except Exception as e:
                                    # Never block on read receipt or typing indicator failure
                                    logger.eprint(f"[WARNING] Failed to send read receipt/typing indicator: {e}")

                                # Mark background task started
                                msg_timing_ctx.mark("background_task_started")

                                # Launch background thread to process message
                                task_manager.execute_async(
                                    process_message,
                                    phone=msg_from,
                                    text=text_body,
                                    message_id=msg_id,
                                    correlation_id=correlation_id,
                                    profile_name=profile_name,
                                    conversation_loader=conversation_loader,
                                    backend_client=backend_client,
                                    whatsapp_client=whatsapp_client,
                                    logger=logger,
                                    query_logger=query_logger,
                                    delivery_tracker=delivery_tracker,
                                    timing_ctx=msg_timing_ctx
                                )
                                logger.eprint(f"[WEBHOOK] Background thread started for message {msg_id}")

                            else:
                                # Unsupported message type
                                logger.eprint(f"\n📱 Unsupported message type: {msg_type} from {msg_from}")
                                whatsapp_client.send_text_message(
                                    msg_from,
                                    "מצטער, אני תומך רק בהודעות טקסט כרגע."
                                )

                    # Process status updates (sent, delivered, read, failed)
                    if "statuses" in value:
                        for status in value["statuses"]:
                            msg_id = status.get("id")
                            status_type = status.get("status")  # sent, delivered, read, failed
                            timestamp_unix = status.get("timestamp")  # Unix timestamp (seconds)
                            recipient_id = status.get("recipient_id")

                            status_info = {
                                "message_id": msg_id,
                                "status": status_type,
                                "timestamp": timestamp_unix,
                                "recipient_id": recipient_id,
                            }
                            logger.log_event("status_update", status_info, webhook_correlation_id)

                            # Check if this message is tracked for delivery timing
                            # Use get() instead of get_and_remove() to preserve tracking for all status updates
                            metadata = delivery_tracker.get(msg_id)
                            if metadata and status_type in ("sent", "delivered", "read"):
                                # Convert timestamp to milliseconds
                                timestamp_ms = float(timestamp_unix) * 1000 if timestamp_unix else None

                                if timestamp_ms:
                                    logger.eprint(
                                        f"[DELIVERY] Status update for {msg_id}: "
                                        f"{status_type} at {timestamp_ms}"
                                    )

                                    # TODO: Update the existing query log entry in GCS with delivery timing
                                    # This would require reading the log, finding the entry by correlation_id,
                                    # updating the timing_breakdown, and writing back.
                                    # For MVP, we just log the event - full implementation can be added later
                                    logger.log_event("delivery_timing", {
                                        "message_id": msg_id,
                                        "correlation_id": metadata["correlation_id"],
                                        "phone": metadata["phone"],
                                        "conversation_id": metadata["conversation_id"],
                                        "sent_timestamp_ms": metadata["sent_timestamp_ms"],
                                        "status_type": status_type,
                                        "status_timestamp_ms": timestamp_ms,
                                        "delivery_latency_ms": timestamp_ms - metadata["sent_timestamp_ms"],
                                    }, metadata["correlation_id"])

                            # Note: Cleanup of delivery tracker entries happens automatically via TTL (30 minutes)
                            # or explicit cleanup_expired() calls. We don't remove entries on status updates
                            # to capture all sequential status changes (sent -> delivered -> read).

            return jsonify({"status": "ok"}), 200

        except Exception as e:
            correlation_id = str(uuid.uuid4())
            logger.eprint(f"[ERROR] {type(e).__name__}: {e}")
            logger.log_event("error", {
                "type": "webhook_handler_exception",
                "error": str(e),
            }, correlation_id)
            # Still return 200 to avoid WhatsApp retries
            return jsonify({"status": "error", "message": str(e)}), 200

    @app.route("/health", methods=["GET"])
    def health_check():
        """
        Health check endpoint.

        Returns:
            JSON response with status and timestamp
        """
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 200

    return app
