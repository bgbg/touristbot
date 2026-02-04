"""
Message processing orchestration.

Handles incoming WhatsApp messages: loads conversation, calls backend QA,
sends images, and delivers responses.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional

from .backend_client import BackendClient
from .conversation import ConversationLoader
from .logging_utils import EventLogger, eprint
from .whatsapp_client import WhatsAppClient


def process_message(
    phone: str,
    text: str,
    message_id: str,
    correlation_id: str,
    conversation_loader: ConversationLoader,
    backend_client: BackendClient,
    whatsapp_client: WhatsAppClient,
    logger: EventLogger
) -> None:
    """
    Process incoming WhatsApp message.

    Main orchestration function for message processing:
    1. Load conversation from GCS
    2. Handle special commands (reset)
    3. Add user message to history
    4. Call backend QA endpoint
    5. Send text response FIRST (fast, within typing indicator window)
    6. Save assistant message to history
    7. Send images AFTER as follow-up (no timeout pressure)

    All errors are caught and logged - this function never raises exceptions to
    prevent crashing the background thread.

    Args:
        phone: User phone number (normalized, digits only)
        text: Message text from user
        message_id: WhatsApp message ID (for logging)
        correlation_id: Request correlation ID for logging
        conversation_loader: Conversation management service
        backend_client: Backend API client
        whatsapp_client: WhatsApp API client
        logger: Event logger

    Example:
        process_message(
            phone="972501234567",
            text="מה יש לראות באגמון?",
            message_id="wamid.123",
            correlation_id="uuid-456",
            conversation_loader=loader,
            backend_client=backend,
            whatsapp_client=whatsapp,
            logger=event_logger
        )
    """
    try:
        eprint(f"\n📱 [ASYNC] Processing message from {phone}: {text[:50]}...")

        # Load conversation
        try:
            conv = conversation_loader.load_conversation(phone)
        except Exception as e:
            eprint(f"[ERROR] Failed to load conversation: {e}")
            whatsapp_client.send_text_message(
                phone,
                "מצטער, אירעה שגיאה בטעינת השיחה. אנא נסה שוב מאוחר יותר."
            )
            return

        # Handle special commands
        response_text = handle_special_command(text, phone, conversation_loader, whatsapp_client)
        if response_text:
            # Command handled, response already sent
            logger.log_event("special_command_handled", {
                "phone": phone,
                "command": text[:20],
            }, correlation_id)
            return

        # Add user message to history (automatically saves to GCS)
        try:
            conversation_loader.conversation_store.add_message(conv, "user", text)
        except Exception as e:
            eprint(f"[ERROR] Failed to save user message: {e}")
            whatsapp_client.send_text_message(
                phone,
                "מצטער, אירעה שגיאה בשמירת ההודעה. אנא נסה שוב."
            )
            return

        # Call backend API
        backend_response = backend_client.call_qa_endpoint(
            conversation_id=conv.conversation_id,
            area=conv.area,
            site=conv.site,
            query=text
        )

        # Validate and extract response
        response_text = backend_response.get("response_text", "מצטער, לא הצלחתי להבין את השאלה.")

        # Defensive type validation for response_text (follow pattern from PR #58)
        if not isinstance(response_text, str):
            eprint(f"[ERROR] response_text is not a string! Type: {type(response_text)}. Converting to string.")
            logger.log_event("error", {
                "type": "invalid_response_text_type",
                "actual_type": str(type(response_text)),
                "value": str(response_text)[:200],
            }, correlation_id)
            response_text = str(response_text)

        # Extract image data
        should_include_images = backend_response.get("should_include_images", False)
        images = backend_response.get("images", [])

        # Defensive validation for images field
        if not isinstance(images, list):
            eprint(f"[WARNING] images field is not a list! Type: {type(images)}. Ignoring images.")
            logger.log_event("error", {
                "type": "invalid_images_type",
                "actual_type": str(type(images)),
            }, correlation_id)
            images = []

        # Send text response FIRST (fast! within typing indicator window)
        eprint(f"[TEXT] Sending text response immediately...")
        status, send_response = whatsapp_client.send_text_message(phone, response_text)

        if status < 200 or status >= 300:
            # Send failed, try fallback error message
            eprint(f"[ERROR] Failed to send response, status: {status}")
            whatsapp_client.send_text_message(
                phone,
                "מצטער, לא הצלחתי לשלוח את התשובה. אנא נסה שוב."
            )
        else:
            eprint(f"✓ [TEXT] Text response sent successfully")

        # Add assistant response to history with images (automatically saves to GCS)
        # This is CRITICAL for duplicate prevention - must save images that were sent
        try:
            conversation_loader.conversation_store.add_message(
                conv,
                "assistant",
                response_text,
                citations=backend_response.get("citations", []),
                images=images if (should_include_images and images) else []
            )
        except Exception as e:
            eprint(f"[ERROR] Failed to save assistant message: {e}")
            # Continue anyway - send images even if save fails

        # Send images AFTER text (as follow-up messages, no timeout pressure)
        # User already has the answer, images are just supplementary
        send_images_if_needed(
            images=images,
            should_include=should_include_images,
            phone=phone,
            whatsapp_client=whatsapp_client,
            correlation_id=correlation_id,
            logger=logger
        )

    except Exception as e:
        # Catch all errors in background thread to prevent crashes
        eprint(f"[ERROR] Background task failed: {type(e).__name__}: {e}")
        logger.log_event("error", {
            "type": "background_task_exception",
            "phone": phone,
            "message_id": message_id,
            "error": str(e),
        }, correlation_id)

        # Try to send error message to user
        try:
            whatsapp_client.send_text_message(
                phone,
                "מצטער, אירעה שגיאה בעיבוד ההודעה. אנא נסה שוב."
            )
        except Exception:
            pass  # Failed to send error message, nothing more we can do


def handle_special_command(
    text: str,
    phone: str,
    conversation_loader: ConversationLoader,
    whatsapp_client: WhatsAppClient
) -> Optional[str]:
    """
    Handle special commands (reset, switch location).

    Args:
        text: Message text from user
        phone: User phone number
        conversation_loader: Conversation management service
        whatsapp_client: WhatsApp API client

    Returns:
        Response text if command was handled, None otherwise

    Example:
        response = handle_special_command("reset", phone, loader, client)
        if response:
            print(f"Command handled: {response}")
    """
    # Reset command
    if text.lower() in ("reset", "התחל מחדש"):
        try:
            conversation_loader.reset_conversation(phone)
            whatsapp_client.send_text_message(phone, "השיחה אופסה. אפשר להתחיל מחדש!")
            eprint("✓ Conversation reset")
            return "השיחה אופסה. אפשר להתחיל מחדש!"
        except Exception as e:
            eprint(f"[ERROR] Failed to reset conversation: {e}")
            whatsapp_client.send_text_message(
                phone,
                "מצטער, לא הצלחתי לאפס את השיחה. אנא נסה שוב."
            )
            return "מצטער, לא הצלחתי לאפס את השיחה."

    # TODO: Handle location switch command (future)
    # if text.lower().startswith("switch to") or text.startswith("עבור ל"):
    #     ...

    return None  # No command matched


def send_images_if_needed(
    images: List[Dict[str, Any]],
    should_include: bool,
    phone: str,
    whatsapp_client: WhatsAppClient,
    correlation_id: str,
    logger: EventLogger
) -> None:
    """
    Send images if available and flagged by LLM.

    Sends only the first image (backend sorted by relevance).
    Performs defensive validation on image data structure.

    Args:
        images: List of image objects from backend
        should_include: Boolean flag from LLM (should images be shown?)
        phone: User phone number
        whatsapp_client: WhatsApp API client
        correlation_id: Request correlation ID for logging
        logger: Event logger

    Example:
        send_images_if_needed(
            images=[{"uri": "https://...", "caption": "שקנאים"}],
            should_include=True,
            phone="972501234567",
            whatsapp_client=client,
            correlation_id="uuid-123",
            logger=event_logger
        )
    """
    if not should_include or not images:
        return

    # Send only the first image (backend sorted by relevance)
    first_image = images[0]

    # Defensive validation: ensure first_image is a dictionary
    if not isinstance(first_image, dict):
        eprint(f"[WARNING] First image entry is not a dict! Type: {type(first_image)}. Skipping image send.")
        logger.log_event("error", {
            "type": "invalid_image_entry_type",
            "actual_type": str(type(first_image)),
        }, correlation_id)
        return

    image_url = first_image.get("uri")  # GCS signed URL
    caption_raw = first_image.get("caption", "")

    # Defensive validation: ensure caption is a string
    if not isinstance(caption_raw, str):
        eprint(f"[WARNING] Caption field is not a string! Type: {type(caption_raw)}. Using empty caption.")
        logger.log_event("error", {
            "type": "invalid_caption_type",
            "actual_type": str(type(caption_raw)),
        }, correlation_id)
        caption = ""
    else:
        caption = caption_raw

    if image_url:
        eprint(f"[IMAGE] Sending image: {caption[:50]}...")
        image_status, image_response = whatsapp_client.send_image(
            phone,
            image_url,
            caption
        )

        if image_status < 200 or image_status >= 300:
            eprint(f"[WARNING] Image send failed, continuing with text response")
            # Don't block text response if image fails
    else:
        eprint(f"[WARNING] Image has no URI, skipping image send")
