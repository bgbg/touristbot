"""
Test QA endpoint with actual API calls.
"""
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
