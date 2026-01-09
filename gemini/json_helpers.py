"""
JSON parsing utilities for handling LLM responses.

Robust JSON extraction that handles:
- Markdown code blocks
- Truncated responses
- Control characters
- Incomplete JSON structures
"""

import json
import re
from typing import Any, Optional


def parse_json(text: str) -> Optional[Any]:
    """
    Parse JSON from text, handling common LLM response formats and truncated responses.

    Args:
        text: Text that may contain JSON

    Returns:
        Parsed JSON object or None if parsing fails
    """
    # Remove markdown code blocks
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*$", "", text)
    text = text.strip()

    # Clean up control characters that can break JSON parsing
    text = text.replace("\r\n", " ")  # Windows line endings
    text = text.replace("\r", " ")  # Mac line endings / standalone CR
    text = text.replace("\n", " ")  # Unix line endings
    text = text.replace("\t", " ")  # Tabs
    # Remove other common control characters
    text = re.sub(r"[\x00-\x1f\x7f]", " ", text)  # All control characters except space
    # Clean up multiple spaces
    text = re.sub(r"\s+", " ", text)

    # Try direct JSON parsing first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Check for truncated JSON (ends with ... or incomplete structure)
    if _is_truncated_json(text):
        # Try to repair truncated JSON
        repaired = _attempt_json_repair(text)
        if repaired:
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass

    # Try to extract JSON from the text
    json_pattern = r"\{.*\}"
    match = re.search(json_pattern, text, re.DOTALL)
    if match:
        json_text = match.group()
        try:
            return json.loads(json_text)
        except json.JSONDecodeError:
            # Try repairing if it looks truncated
            if _is_truncated_json(json_text):
                repaired = _attempt_json_repair(json_text)
                if repaired:
                    try:
                        return json.loads(repaired)
                    except json.JSONDecodeError:
                        pass

    # Try to extract JSON array (most common for topic lists)
    array_pattern = r"\[.*\]"
    match = re.search(array_pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


def _is_truncated_json(text: str) -> bool:
    """
    Detect if JSON appears to be truncated.

    Args:
        text: JSON text to check

    Returns:
        True if the JSON appears truncated
    """
    text = text.strip()

    # Check for common truncation indicators
    truncation_indicators = [
        "...",  # Explicit truncation
        "…",  # Unicode ellipsis
    ]

    for indicator in truncation_indicators:
        if indicator in text:
            return True

    # Check for incomplete JSON structure
    if text.startswith("{") and not text.endswith("}"):
        return True
    if text.startswith("[") and not text.endswith("]"):
        return True

    # Check for incomplete string values (unclosed quotes)
    # Count quotes to see if they're balanced
    quote_count = text.count('"') - text.count('\\"')  # Exclude escaped quotes
    if quote_count % 2 != 0:
        return True

    return False


def _attempt_json_repair(text: str) -> Optional[str]:
    """
    Attempt to repair truncated JSON by completing common patterns.

    Args:
        text: Truncated JSON text

    Returns:
        Repaired JSON string or None if repair not possible
    """
    text = text.strip()

    # Remove explicit truncation indicators
    text = re.sub(r"\.\.\.+$", "", text)
    text = re.sub(r"…+$", "", text)

    # For JSON arrays (most common for topic lists)
    if text.startswith("["):
        # Find the last complete string entry
        # Pattern: find all complete strings in array
        complete_items = []
        item_pattern = r'"([^"]+)"'
        for match in re.finditer(item_pattern, text):
            complete_items.append(match.group(1))

        if complete_items:
            # Build a valid array from complete items
            return "[" + ", ".join([f'"{item}"' for item in complete_items]) + "]"

    # For JSON objects
    if text.startswith("{"):
        # Find any complete key-value pairs
        complete_fields = []
        field_pattern = r'"([^"]+)":\s*"([^"]*)"'
        for match in re.finditer(field_pattern, text):
            field_name = match.group(1)
            field_value = match.group(2)
            # Only include if the field looks complete
            if not field_value.endswith("...") and not field_value.endswith("…"):
                complete_fields.append((field_name, field_value))

        if complete_fields:
            # Build JSON from complete fields
            json_parts = [f'"{name}": "{value}"' for name, value in complete_fields]
            return "{" + ", ".join(json_parts) + "}"

    return None
