#!/usr/bin/env python3
"""
Test script for display name encoding/decoding utilities
"""

from gemini.display_name_utils import (
    encode_display_name,
    parse_display_name,
    is_encoded_display_name,
    _sanitize_name,
)


def test_sanitize_name():
    """Test name sanitization"""
    print("Testing _sanitize_name()...")

    tests = [
        ("Tel Aviv District", "tel_aviv_district"),
        ("  Old  City  ", "old_city"),
        ("Jaffa-Port", "jaffa_port"),
        ("Nature Reserve #1", "nature_reserve_1"),
        ("Museum_Park", "museum_park"),
        ("test", "test"),
    ]

    for input_name, expected in tests:
        result = _sanitize_name(input_name)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{input_name}' → '{result}' (expected: '{expected}')")

    print()


def test_encode_decode():
    """Test encoding and decoding"""
    print("Testing encode_display_name() and parse_display_name()...")

    tests = [
        ("tel_aviv", "jaffa_port", "historical_tour_chunk_001.txt"),
        ("old_city", "western_wall", "guide.txt"),
        ("nature reserve", "hiking trails", "map_chunk_005.txt"),
        ("Museum District", "National Museum", "artifact_info.txt"),
    ]

    for area, site, filename in tests:
        # Encode
        encoded = encode_display_name(area, site, filename)
        print(f"\n  Encoded: area='{area}', site='{site}', file='{filename}'")
        print(f"    → '{encoded}'")

        # Decode
        parsed = parse_display_name(encoded)
        if parsed:
            parsed_area, parsed_site, parsed_filename = parsed
            match = (
                _sanitize_name(area) == parsed_area
                and _sanitize_name(site) == parsed_site
                and filename == parsed_filename
            )
            status = "✓" if match else "✗"
            print(f"    {status} Decoded: area='{parsed_area}', site='{parsed_site}', file='{parsed_filename}'")
        else:
            print(f"    ✗ Failed to decode!")

    print()


def test_parse_legacy_names():
    """Test parsing legacy display names (without encoding)"""
    print("Testing parse_display_name() with legacy names...")

    legacy_names = [
        "historical_tour_chunk_001.txt",
        "park_guide.txt",
        "simple_file.md",
    ]

    for name in legacy_names:
        parsed = parse_display_name(name)
        is_encoded = is_encoded_display_name(name)
        status = "✓" if parsed is None and not is_encoded else "✗"
        print(f"  {status} '{name}' → {parsed} (encoded: {is_encoded})")

    print()


def test_edge_cases():
    """Test edge cases"""
    print("Testing edge cases...")

    # Filename with delimiter in it
    encoded = encode_display_name("test_area", "test_site", "file__with__delimiters.txt")
    parsed = parse_display_name(encoded)
    if parsed:
        area, site, filename = parsed
        status = "✓" if filename == "file__with__delimiters.txt" else "✗"
        print(f"  {status} Filename with delimiters: '{filename}'")
    else:
        print(f"  ✗ Failed to parse filename with delimiters")

    # Very long names (should not exceed 512 chars)
    try:
        long_area = "a" * 200
        long_site = "b" * 200
        long_filename = "c" * 200
        encoded = encode_display_name(long_area, long_site, long_filename)
        print(f"  ✗ Should have raised ValueError for long name (got {len(encoded)} chars)")
    except ValueError as e:
        print(f"  ✓ Correctly raised ValueError for long name")

    # Empty components
    try:
        encoded = encode_display_name("", "site", "file.txt")
        parsed = parse_display_name(encoded)
        status = "✓" if parsed is None else "✗"
        print(f"  {status} Empty area handled correctly")
    except Exception as e:
        print(f"  ✓ Empty area raised exception: {e}")

    print()


def test_real_world_examples():
    """Test with actual chunk filenames from the API"""
    print("Testing with real-world chunk filenames...")

    real_filenames = [
        "historical_tour_chunk_006.txt",
        "historical_tour_he_chunk_020.txt",
        "park_guide_he_chunk_019.txt",
        "hiking_trails_chunk_004.txt",
        "nature_reserve_chunk_003.txt",
    ]

    for filename in real_filenames:
        # These should NOT be recognized as encoded (legacy files)
        is_encoded = is_encoded_display_name(filename)
        status = "✓" if not is_encoded else "✗"
        print(f"  {status} '{filename}' → legacy (not encoded)")

    print("\nNow testing same filenames WITH encoding...")
    for filename in real_filenames:
        encoded = encode_display_name("jerusalem", "old_city", filename)
        parsed = parse_display_name(encoded)

        if parsed:
            area, site, parsed_filename = parsed
            status = "✓" if (area == "jerusalem" and site == "old_city" and parsed_filename == filename) else "✗"
            print(f"  {status} '{encoded}' → area='{area}', site='{site}', file='{parsed_filename}'")
        else:
            print(f"  ✗ Failed to parse: '{encoded}'")

    print()


if __name__ == "__main__":
    print("=" * 70)
    print("DISPLAY NAME ENCODING/DECODING TESTS")
    print("=" * 70)
    print()

    test_sanitize_name()
    test_encode_decode()
    test_parse_legacy_names()
    test_edge_cases()
    test_real_world_examples()

    print("=" * 70)
    print("ALL TESTS COMPLETED")
    print("=" * 70)
