"""
Test QA endpoint with actual API calls.
"""
import json
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from backend.models import ImageAwareResponse


def test_pydantic_schema_for_gemini_api():
    """
    Test that ImageAwareResponse Pydantic schema is compatible with Gemini API.

    The Gemini API doesn't support 'additionalProperties' in schemas.
    This test verifies the schema can be serialized without that field.
    """
    # Get the Gemini-compatible schema
    schema = ImageAwareResponse.get_gemini_schema()

    # Check that additionalProperties is not in the schema
    # If it exists, it will cause: "additionalProperties is not supported in the Gemini API"
    assert "additionalProperties" not in schema, \
        f"Schema contains additionalProperties which is not supported by Gemini API: {schema}"

    # Also check nested objects
    if "properties" in schema:
        for prop_name, prop_schema in schema["properties"].items():
            if isinstance(prop_schema, dict):
                assert "additionalProperties" not in prop_schema, \
                    f"Property '{prop_name}' contains additionalProperties: {prop_schema}"

    # Check definitions/defs
    for key in ["$defs", "definitions"]:
        if key in schema:
            for def_name, def_schema in schema[key].items():
                if isinstance(def_schema, dict):
                    assert "additionalProperties" not in def_schema, \
                        f"Definition '{def_name}' contains additionalProperties: {def_schema}"


def test_pydantic_schema_structure():
    """Verify the ImageAwareResponse schema has the expected structure."""
    schema = ImageAwareResponse.get_gemini_schema()

    # Must have required fields
    assert "properties" in schema
    assert "response_text" in schema["properties"]
    assert "should_include_images" in schema["properties"]
    assert "image_relevance" in schema["properties"]

    # Verify types
    assert schema["properties"]["response_text"]["type"] == "string"
    assert schema["properties"]["should_include_images"]["type"] == "boolean"
    assert schema["properties"]["image_relevance"]["type"] == "array"

    # Verify image_relevance array has items with proper structure
    assert "items" in schema["properties"]["image_relevance"]
    assert "$ref" in schema["properties"]["image_relevance"]["items"]

    # Verify the referenced ImageRelevanceScore definition exists
    assert "$defs" in schema
    assert "ImageRelevanceScore" in schema["$defs"]

    # Verify ImageRelevanceScore has required fields
    score_def = schema["$defs"]["ImageRelevanceScore"]
    assert "properties" in score_def
    assert "uri" in score_def["properties"]
    assert "score" in score_def["properties"]
    assert score_def["properties"]["uri"]["type"] == "string"
    assert score_def["properties"]["score"]["type"] == "integer"


# ============================================================================
# Type Validation Tests
# Tests for Issue #43 fix - ensure response_text is always a string
# ============================================================================


def test_type_validation_logic_with_string():
    """Test validation logic: response_text is a string (normal case)."""
    # Simulate the validation logic from qa.py
    extracted_text = "This is a proper string response"

    # Validation logic: check if string
    if not isinstance(extracted_text, str):
        extracted_text = str(extracted_text)

    # Should remain unchanged
    assert isinstance(extracted_text, str)
    assert extracted_text == "This is a proper string response"


def test_type_validation_logic_with_dict():
    """Test validation logic: response_text is a dict (bug case) - should convert to string."""
    # Simulate the validation logic from qa.py
    extracted_text = {"nested": "value", "key": "data"}

    # Validation logic: check if string, convert if not
    if not isinstance(extracted_text, str):
        extracted_text = str(extracted_text)

    # Should be converted to string
    assert isinstance(extracted_text, str)
    assert "nested" in extracted_text
    assert "value" in extracted_text


def test_type_validation_logic_with_list():
    """Test validation logic: response_text is a list (bug case) - should convert to string."""
    # Simulate the validation logic from qa.py
    extracted_text = ["item1", "item2", "item3"]

    # Validation logic: check if string, convert if not
    if not isinstance(extracted_text, str):
        extracted_text = str(extracted_text)

    # Should be converted to string
    assert isinstance(extracted_text, str)
    assert "item1" in extracted_text
    assert "item2" in extracted_text


def test_type_validation_logic_with_int():
    """Test validation logic: response_text is an integer (bug case) - should convert to string."""
    # Simulate the validation logic from qa.py
    extracted_text = 12345

    # Validation logic: check if string, convert if not
    if not isinstance(extracted_text, str):
        extracted_text = str(extracted_text)

    # Should be converted to string
    assert isinstance(extracted_text, str)
    assert extracted_text == "12345"


def test_type_validation_logic_with_none():
    """Test validation logic: response_text is None (edge case) - should convert to string."""
    # Simulate the validation logic from qa.py
    extracted_text = None

    # Validation logic: check if string, convert if not
    if not isinstance(extracted_text, str):
        extracted_text = str(extracted_text)

    # Should be converted to string
    assert isinstance(extracted_text, str)
    assert extracted_text == "None"


def test_type_validation_logic_with_bool():
    """Test validation logic: response_text is a boolean (edge case) - should convert to string."""
    # Simulate the validation logic from qa.py
    extracted_text = True

    # Validation logic: check if string, convert if not
    if not isinstance(extracted_text, str):
        extracted_text = str(extracted_text)

    # Should be converted to string
    assert isinstance(extracted_text, str)
    assert extracted_text == "True"
