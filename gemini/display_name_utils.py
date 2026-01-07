"""
Display Name Utilities - Encoding/decoding area/site metadata in file display names

This module provides utilities to encode area/site information in file display names
when uploading to Gemini Files API, and to parse them back when rebuilding the registry.

Format: {area}__{site}__{original_filename}
Example: "tel_aviv__jaffa_port__historical_tour_chunk_001.txt"
"""

import re
from typing import Optional, Tuple


# Delimiter used to separate area, site, and filename
DELIMITER = "__"


def encode_display_name(area: str, site: str, filename: str) -> str:
    """
    Encode area/site metadata into a display name for file upload

    Args:
        area: Area name (e.g., "tel_aviv", "Old City")
        site: Site name (e.g., "jaffa_port", "Western Wall")
        filename: Original filename (e.g., "historical_tour_chunk_001.txt")

    Returns:
        Encoded display name with format: {area}__{site}__{filename}

    Raises:
        ValueError: If area/site become empty after sanitization or encoded name exceeds 512 chars

    Examples:
        >>> encode_display_name("tel_aviv", "jaffa_port", "tour_chunk_001.txt")
        'tel_aviv__jaffa_port__tour_chunk_001.txt'

        >>> encode_display_name("Old City", "Western Wall", "guide.txt")
        'old_city__western_wall__guide.txt'
    """
    # Sanitize area and site names: lowercase, replace spaces with underscores
    area_clean = _sanitize_name(area)
    site_clean = _sanitize_name(site)

    # Validate that sanitized names are not empty
    if not area_clean:
        raise ValueError(f"Area name '{area}' becomes empty after sanitization")
    if not site_clean:
        raise ValueError(f"Site name '{site}' becomes empty after sanitization")

    # Build encoded name
    encoded = f"{area_clean}{DELIMITER}{site_clean}{DELIMITER}{filename}"

    # Validate length (Gemini API limit: 512 characters)
    if len(encoded) > 512:
        raise ValueError(
            f"Encoded display name too long ({len(encoded)} chars). "
            f"Must be ≤512 characters. Consider shorter area/site names."
        )

    return encoded


def parse_display_name(display_name: str) -> Optional[Tuple[str, str, str]]:
    """
    Parse area/site metadata from an encoded display name

    Args:
        display_name: Encoded display name from Gemini Files API

    Returns:
        Tuple of (area, site, filename) if successfully parsed, None otherwise

    Examples:
        >>> parse_display_name("tel_aviv__jaffa_port__tour_chunk_001.txt")
        ('tel_aviv', 'jaffa_port', 'tour_chunk_001.txt')

        >>> parse_display_name("old_city__western_wall__guide.txt")
        ('old_city', 'western_wall', 'guide.txt')

        >>> parse_display_name("legacy_file_without_encoding.txt")
        None
    """
    if not display_name:
        return None

    # Split by delimiter
    parts = display_name.split(DELIMITER)

    # Need at least 3 parts: area, site, filename
    if len(parts) < 3:
        return None

    # Extract components
    area = parts[0]
    site = parts[1]
    # Filename may contain delimiters, so rejoin remaining parts
    filename = DELIMITER.join(parts[2:])

    # Validate that area and site are non-empty
    if not area or not site:
        return None

    return (area, site, filename)


def _sanitize_name(name: str) -> str:
    """
    Sanitize area/site name for use in display names

    - Convert to lowercase
    - Replace spaces and special characters with underscores
    - Remove consecutive underscores
    - Remove leading/trailing underscores

    Args:
        name: Original area or site name

    Returns:
        Sanitized name safe for use in filenames

    Examples:
        >>> _sanitize_name("Tel Aviv District")
        'tel_aviv_district'

        >>> _sanitize_name("  Old  City  ")
        'old_city'

        >>> _sanitize_name("Jaffa-Port")
        'jaffa_port'
    """
    # Convert to lowercase
    name = name.lower()

    # Replace spaces and hyphens with underscores
    name = name.replace(' ', '_').replace('-', '_')

    # Replace any other non-alphanumeric characters (except underscore) with underscore
    name = re.sub(r'[^a-z0-9_]', '_', name)

    # Collapse multiple consecutive underscores into one
    name = re.sub(r'_+', '_', name)

    # Remove leading and trailing underscores
    name = name.strip('_')

    return name


def is_encoded_display_name(display_name: str) -> bool:
    """
    Check if a display name contains encoded area/site metadata

    Args:
        display_name: Display name to check

    Returns:
        True if display name appears to be encoded with area/site metadata

    Examples:
        >>> is_encoded_display_name("tel_aviv__jaffa_port__tour.txt")
        True

        >>> is_encoded_display_name("legacy_file.txt")
        False
    """
    return parse_display_name(display_name) is not None
