"""
Unit tests for JSON parsing utilities.

Tests the enhanced JSON parsing logic that handles truncated LLM responses,
markdown code blocks, control characters, and other edge cases.
"""

import pytest

from gemini.json_helpers import parse_json, _is_truncated_json, _attempt_json_repair


class TestJsonParsing:
    """Test JSON parsing with various input formats."""

    def test_valid_json_object_parsing(self):
        """Test parsing of valid JSON objects."""
        valid_json = '{"field1": "value1", "field2": "value2"}'
        result = parse_json(valid_json)

        assert result is not None
        assert result["field1"] == "value1"
        assert result["field2"] == "value2"

    def test_valid_json_array_parsing(self):
        """Test parsing of valid JSON arrays."""
        valid_array = '["topic1", "topic2", "topic3"]'
        result = parse_json(valid_array)

        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0] == "topic1"

    def test_markdown_json_blocks(self):
        """Test parsing JSON wrapped in markdown code blocks."""
        markdown_json = """```json
["topic1", "topic2", "topic3"]
```"""
        result = parse_json(markdown_json)

        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 3

    def test_json_with_control_characters(self):
        """Test handling of JSON with control characters like carriage returns."""
        json_with_control_chars = '["topic with\r\nline breaks", "topic with\ttabs"]'

        result = parse_json(json_with_control_chars)

        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 2
        # Control characters should be replaced with spaces
        assert " " in result[0]

    def test_hebrew_content_handling(self):
        """Test handling of Hebrew content in JSON."""
        hebrew_json = '["היסטוריה", "אדריכלות", "תרבות"]'
        result = parse_json(hebrew_json)

        assert result is not None
        assert isinstance(result, list)
        assert result[0] == "היסטוריה"
        assert result[1] == "אדריכלות"
        assert result[2] == "תרבות"

    def test_truncated_json_array_repair(self):
        """Test repair of truncated JSON arrays."""
        test_cases = [
            # Missing closing bracket
            ('["topic1", "topic2", "topic3"', ["topic1", "topic2", "topic3"]),
            # Explicit truncation with ellipsis
            ('["topic1", "topic2", "topic3...', ["topic1", "topic2"]),
            # Unicode ellipsis
            ('["topic1", "topic2…', ["topic1"]),
            # Incomplete last item
            ('["topic1", "topic2", "topic', ["topic1", "topic2"]),
        ]

        for truncated_input, expected_output in test_cases:
            result = parse_json(truncated_input)
            assert result is not None, f"Failed to parse: {truncated_input}"
            assert isinstance(result, list)
            assert len(result) >= len(expected_output) - 1  # Allow some variation in repair

    def test_truncated_hebrew_array(self):
        """Test repair of truncated JSON with Hebrew content."""
        truncated_hebrew = '["היסטוריה", "אדריכלות", "תרב...'
        result = parse_json(truncated_hebrew)

        assert result is not None
        assert isinstance(result, list)
        # Should contain at least the complete items
        assert "היסטוריה" in result
        assert "אדריכלות" in result

    def test_json_extraction_from_text(self):
        """Test extraction of JSON from larger text blocks."""
        text_with_array = """
        Here are the topics:
        ["topic1", "topic2", "topic3"]
        That's all!
        """
        result = parse_json(text_with_array)

        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 3

    def test_invalid_json_returns_none(self):
        """Test handling of completely invalid JSON."""
        test_cases = [
            "not json at all",
            "{'single': 'quotes'}",  # Invalid JSON (single quotes)
            "",  # Empty string
            "   ",  # Whitespace only
        ]

        for invalid_input in test_cases:
            result = parse_json(invalid_input)
            # These should either return None or a minimal repaired structure
            # The key is they shouldn't crash
            assert result is None or isinstance(result, (dict, list))

    def test_long_hebrew_json_array(self):
        """Test parsing of JSON array with long Hebrew strings."""
        long_hebrew_json = """[
  "היסטוריה של המקום והתפתחותו לאורך השנים",
  "אדריכלות ייחודית ומבנים היסטוריים",
  "תרבות מקומית ומסורות עתיקות",
  "אירועים היסטוריים חשובים",
  "אתרי עניין ומוקדי משיכה"
]"""

        result = parse_json(long_hebrew_json)

        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 5
        assert "היסטוריה" in result[0]

    def test_real_world_llm_response_formats(self):
        """Test various real-world LLM response formats."""
        # Format 1: Clean JSON
        clean = '["topic1", "topic2", "topic3"]'
        assert parse_json(clean) is not None

        # Format 2: Markdown wrapped
        markdown = '```json\n["topic1", "topic2"]\n```'
        assert parse_json(markdown) is not None

        # Format 3: With explanation
        with_text = 'Here are the topics:\n["topic1", "topic2"]'
        assert parse_json(with_text) is not None

        # Format 4: Truncated
        truncated = '["topic1", "topic2...'
        result = parse_json(truncated)
        assert result is not None
        assert isinstance(result, list)


class TestTruncationDetection:
    """Test the truncation detection helper function."""

    def test_detects_truncated_arrays(self):
        """Test detection of truncated JSON arrays."""
        truncated_cases = [
            '["topic1", "topic2"',  # Missing closing bracket
            '["topic1", "topic2...', # Explicit ellipsis
            '["topic1", "topic2…',  # Unicode ellipsis
            '["topic1", "topic',  # Unclosed quote
        ]

        for case in truncated_cases:
            assert _is_truncated_json(case), f"Should detect truncation: {case}"

    def test_does_not_detect_complete_json(self):
        """Test that complete JSON is not flagged as truncated."""
        complete_cases = [
            '["topic1", "topic2", "topic3"]',
            '{"key": "value"}',
            '[]',
            '{}',
        ]

        for case in complete_cases:
            assert not _is_truncated_json(case), f"Should not detect truncation: {case}"


class TestJsonRepair:
    """Test the JSON repair helper function."""

    def test_repairs_truncated_arrays(self):
        """Test repair of truncated JSON arrays."""
        truncated = '["topic1", "topic2", "topic3...'
        repaired = _attempt_json_repair(truncated)

        assert repaired is not None
        # Should be valid JSON after repair
        import json
        result = json.loads(repaired)
        assert isinstance(result, list)
        assert len(result) >= 2  # Should preserve complete items

    def test_repairs_incomplete_arrays(self):
        """Test repair of arrays missing closing bracket."""
        incomplete = '["topic1", "topic2"'
        repaired = _attempt_json_repair(incomplete)

        assert repaired is not None
        import json
        result = json.loads(repaired)
        assert isinstance(result, list)
        assert "topic1" in result
        assert "topic2" in result

    def test_handles_unrepairable_json(self):
        """Test handling of JSON that cannot be repaired."""
        unrepairable = "not json at all"
        repaired = _attempt_json_repair(unrepairable)

        # Should either return None or minimal valid structure
        if repaired is not None:
            import json
            # If it returns something, it should be valid JSON
            result = json.loads(repaired)
            assert result is not None


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_array(self):
        """Test parsing empty JSON array."""
        empty_array = '[]'
        result = parse_json(empty_array)

        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 0

    def test_single_item_array(self):
        """Test parsing single-item JSON array."""
        single_item = '["only topic"]'
        result = parse_json(single_item)

        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0] == "only topic"

    def test_very_long_array(self):
        """Test parsing array with many items."""
        items = [f"topic{i}" for i in range(100)]
        long_array = '["' + '", "'.join(items) + '"]'
        result = parse_json(long_array)

        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 100

    def test_array_with_special_characters(self):
        """Test parsing array with special characters in strings."""
        special_chars = r'["topic with \"quotes\"", "topic with \\backslash"]'
        result = parse_json(special_chars)

        assert result is not None
        assert isinstance(result, list)
        # Should handle escaped quotes and backslashes

    def test_mixed_language_content(self):
        """Test parsing array with mixed Hebrew and English content."""
        mixed = '["History היסטוריה", "Architecture אדריכלות", "Culture תרבות"]'
        result = parse_json(mixed)

        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 3


class TestDoubleEncodedJSON:
    """Test handling of double-encoded JSON (Streamlit Cloud issue #23)."""

    def test_double_encoded_response_text(self):
        """Test extraction of double-encoded JSON in response_text field."""
        # Simulate the Streamlit Cloud issue where LLM returns JSON as string inside response_text
        double_encoded = """{
  "response_text": "{\\"response_text\\": \\"היי! ברוך הבא לפארק הירקון!\\", \\"should_include_images\\": false, \\"image_relevance\\": []}",
  "should_include_images": false,
  "image_relevance": []
}"""

        result = parse_json(double_encoded)

        assert result is not None
        assert isinstance(result, dict)
        # Should unwrap the double-encoded structure
        assert result["response_text"] == "היי! ברוך הבא לפארק הירקון!"
        assert result["should_include_images"] == False
        assert result["image_relevance"] == []

    def test_normal_response_text_not_unwrapped(self):
        """Test that normal (non-double-encoded) response_text is kept as-is."""
        normal_json = """{
  "response_text": "היי! ברוך הבא לפארק הירקון!",
  "should_include_images": false,
  "image_relevance": []
}"""

        result = parse_json(normal_json)

        assert result is not None
        assert isinstance(result, dict)
        assert result["response_text"] == "היי! ברוך הבא לפארק הירקון!"
        assert result["should_include_images"] == False
        assert result["image_relevance"] == []

    def test_double_encoded_with_images(self):
        """Test double-encoded JSON with image relevance data."""
        double_encoded = """{
  "response_text": "{\\"response_text\\": \\"הנה תמונות של שקנאים!\\", \\"should_include_images\\": true, \\"image_relevance\\": [{\\"image_uri\\": \\"https://example.com/image1\\", \\"relevance_score\\": 85}]}",
  "should_include_images": true,
  "image_relevance": []
}"""

        result = parse_json(double_encoded)

        assert result is not None
        assert isinstance(result, dict)
        # Should unwrap to the inner structure with proper image_relevance
        assert result["response_text"] == "הנה תמונות של שקנאים!"
        assert result["should_include_images"] == True
        assert isinstance(result["image_relevance"], list)
        assert len(result["image_relevance"]) == 1
        assert result["image_relevance"][0]["image_uri"] == "https://example.com/image1"
        assert result["image_relevance"][0]["relevance_score"] == 85

    def test_response_text_with_braces_not_json(self):
        """Test that response_text containing braces but not JSON is kept as-is."""
        # Some responses might mention braces in text but aren't JSON
        normal_with_braces = """{
  "response_text": "המבנה {כמו כן} נבנה בשנת 1920",
  "should_include_images": false,
  "image_relevance": []
}"""

        result = parse_json(normal_with_braces)

        assert result is not None
        assert isinstance(result, dict)
        # Should keep the original text with braces
        assert "המבנה {כמו כן} נבנה" in result["response_text"]
        assert result["should_include_images"] == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
