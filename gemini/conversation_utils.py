#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Conversation history utilities for message format conversion
"""

from google.genai import types


def convert_messages_to_gemini_format(messages: list[dict]) -> list[types.Content]:
    """
    Convert messages from session state format to Gemini API format

    This function:
    - Implements a sliding window (keeps only last 10 messages)
    - Maps "assistant" role to "model" for Gemini API compatibility
    - Accepts "model" role directly for API format compatibility
    - Strips metadata fields (time, etc.)
    - Filters out messages with invalid roles or empty content

    Args:
        messages: List of message dicts with 'role' and 'content' keys

    Returns:
        List of Content objects suitable for Gemini API
    """
    # Implement sliding window: keep only last 10 messages to limit token usage
    recent_messages = messages[-10:] if len(messages) > 10 else messages

    # Convert messages to Gemini API format
    conversation_history = []
    for msg in recent_messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        # Skip messages with empty content
        if not content:
            continue

        # Map "assistant" to "model" for Gemini API compatibility
        # Also allow "model" role for direct API format compatibility
        if role == "assistant":
            role = "model"
        elif role not in ["user", "model"]:
            # Skip messages with invalid roles
            continue

        # Strip metadata fields (time, etc.) and only pass role and content
        conversation_history.append(
            types.Content(role=role, parts=[types.Part.from_text(text=content)])
        )

    return conversation_history
