#!/usr/bin/env python3
"""
QR Code generator for WhatsApp messages.
Creates QR codes that open WhatsApp with a pre-filled message.

What can be sent via WhatsApp URL (wa.me):
✅ Text message (pre-filled) - use ?text= parameter
✅ Location (as Google Maps link in text) - embed maps URL in message
✅ Phone number to start chat
✅ Empty message (just open chat)

What CANNOT be sent directly via wa.me URL:
❌ Images/photos - WhatsApp API doesn't support image URLs in wa.me links
❌ Videos - Not supported in wa.me links
❌ Documents/PDFs - Not supported in wa.me links
❌ Native location pins - Can only embed Google Maps links as text
❌ Contacts/vCards - Not supported in wa.me links
❌ Voice messages - Not supported

For sending media (images, videos, documents):
- Need WhatsApp Business API (paid service)
- Or use WhatsApp Cloud API
- Or user must manually attach after QR scan opens the chat

Workarounds for "sending" media via QR:
- Embed links to images/documents in the message text
- User clicks link to view/download
- Example: "Check out this image: https://example.com/image.jpg"
"""

import qrcode
from urllib.parse import quote
from typing import Optional


def generate_qr_for_whatsapp(
    phone_number: str, initial_text: str = "", output_file: str = "whatsapp_qr.png"
):
    """
    Generate a QR code for WhatsApp message with text.

    Args:
        phone_number: Phone number in international format (e.g., "972587262286")
        initial_text: Pre-filled message text
        output_file: Output filename for the QR code image

    Returns:
        str: Path to the generated QR code image
    """
    # Clean phone number - remove spaces, dashes, and leading zeros
    clean_number = phone_number.replace(" ", "").replace("-", "").replace("+", "")

    # If Israeli number starting with 0, convert to international format
    if clean_number.startswith("05"):
        clean_number = "972" + clean_number[1:]

    # URL encode the message text
    encoded_text = quote(initial_text)

    # Create WhatsApp URL
    whatsapp_url = f"https://wa.me/{clean_number}?text={encoded_text}"

    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(whatsapp_url)
    qr.make(fit=True)

    # Create image
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(output_file)

    print(f"QR code generated: {output_file}")
    print(f"WhatsApp URL: {whatsapp_url}")

    return output_file


def generate_qr_for_whatsapp_with_location(
    phone_number: str,
    latitude: float,
    longitude: float,
    location_name: Optional[str] = None,
    message: str = "",
    output_file: str = "whatsapp_location_qr.png",
):
    """
    Generate a QR code for WhatsApp with a location link in the message.

    Note: WhatsApp doesn't support direct location sharing via URL.
    This embeds a Google Maps link in the message text.

    Args:
        phone_number: Phone number in international format
        latitude: Location latitude
        longitude: Location longitude
        location_name: Optional name/description of the location
        message: Additional message text before the location link
        output_file: Output filename for the QR code image

    Returns:
        str: Path to the generated QR code image
    """
    # Build location URL (Google Maps format)
    maps_url = f"https://maps.google.com/?q={latitude},{longitude}"

    # Build message with location
    full_message = message
    if location_name:
        full_message += f"\n📍 {location_name}\n{maps_url}"
    else:
        full_message += f"\n📍 {maps_url}"

    return generate_qr_for_whatsapp(phone_number, full_message, output_file)


if __name__ == "__main__":
    # Example 1: Simple text message
    phone = "058-7262286"
    # message = "היוש. זאת בדיקה"
    # generate_qr_for_whatsapp(phone, message, "tmp.png")

    # Example 2: Message with location (Google Maps link embedded)
    # Agamon Hula coordinates as an example
    generate_qr_for_whatsapp_with_location(
        phone,
        latitude=33.1167,
        longitude=35.6167,
        location_name="אגמון החולה",
        message="שלום! רציתי לשתף איתך את המיקום:",
        output_file="tmp.png",
    )

    # Example 3: Just open chat (no pre-filled text)
    # generate_qr_for_whatsapp(phone, "", "whatsapp_empty_qr.png")
