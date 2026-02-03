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

@pytest.fixture
def test_client_with_mocks():
    """Create test client with mocked environment and dependencies."""
    import os

    # Set required environment variables
    os.environ["GCS_BUCKET"] = "test-bucket"
    os.environ["BACKEND_API_KEYS"] = "test-key"
    os.environ["GOOGLE_API_KEY"] = "test-google-key"

    from backend.main import app
    client = TestClient(app)

    yield client

    # Cleanup
    os.environ.pop("GCS_BUCKET", None)
    os.environ.pop("BACKEND_API_KEYS", None)
    os.environ.pop("GOOGLE_API_KEY", None)


def create_mock_gemini_response(response_text_value, response_text_type="string"):
    """
    Helper to create a mock Gemini API response.

    Args:
        response_text_value: The value to use for response_text
        response_text_type: "string", "dict", "list", "int" to control the type
    """
    mock_response = MagicMock()
    mock_response.text = ""
    mock_response.grounding_metadata = None

    # Create structured JSON response based on type
    if response_text_type == "string":
        # Normal case: response_text is a string
        json_response = {
            "response_text": response_text_value,
            "should_include_images": True,
            "image_relevance": []
        }
    elif response_text_type == "dict":
        # Bug case: response_text is a dict instead of string
        json_response = {
            "response_text": {"nested": response_text_value},
            "should_include_images": True,
            "image_relevance": []
        }
    elif response_text_type == "list":
        # Bug case: response_text is a list
        json_response = {
            "response_text": [response_text_value],
            "should_include_images": True,
            "image_relevance": []
        }
    elif response_text_type == "int":
        # Bug case: response_text is an integer
        json_response = {
            "response_text": 12345,
            "should_include_images": True,
            "image_relevance": []
        }

    mock_response.text = json.dumps(json_response)
    return mock_response


@patch("backend.endpoints.qa.get_image_registry")
@patch("backend.endpoints.qa.get_conversation_store")
@patch("backend.endpoints.qa.get_store_registry")
@patch("backend.endpoints.qa.get_storage_backend")
@patch("backend.endpoints.qa.genai.GenerativeModel")
def test_type_validation_with_string_response(
    mock_model, mock_storage, mock_store_reg, mock_conv_store, mock_img_reg, test_client_with_mocks
):
    """Test normal case: response_text is a string (no validation needed)."""
    # Setup mocks
    mock_store_reg.return_value.get_store_name.return_value = "test-store"
    mock_img_reg.return_value.get_images.return_value = []
    mock_conv_store.return_value.load_conversation.return_value = []

    # Mock Gemini API to return proper string response
    mock_instance = MagicMock()
    mock_model.return_value = mock_instance
    mock_instance.generate_content.return_value = create_mock_gemini_response(
        "This is a proper string response", response_text_type="string"
    )

    # Make request
    response = test_client_with_mocks.post(
        "/qa",
        headers={"Authorization": "Bearer test-key"},
        json={"area": "test_area", "site": "test_site", "query": "test query"}
    )

    # Should succeed with 200
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["response_text"], str)
    assert data["response_text"] == "This is a proper string response"


@patch("backend.endpoints.qa.get_image_registry")
@patch("backend.endpoints.qa.get_conversation_store")
@patch("backend.endpoints.qa.get_store_registry")
@patch("backend.endpoints.qa.get_storage_backend")
@patch("backend.endpoints.qa.genai.GenerativeModel")
@patch("backend.endpoints.qa.logger")
def test_type_validation_with_dict_response(
    mock_logger, mock_model, mock_storage, mock_store_reg, mock_conv_store, mock_img_reg, test_client_with_mocks
):
    """Test validation when response_text is a dict - should convert to string and log error."""
    # Setup mocks
    mock_store_reg.return_value.get_store_name.return_value = "test-store"
    mock_img_reg.return_value.get_images.return_value = []
    mock_conv_store.return_value.load_conversation.return_value = []

    # Mock Gemini API to return dict instead of string
    mock_instance = MagicMock()
    mock_model.return_value = mock_instance
    mock_instance.generate_content.return_value = create_mock_gemini_response(
        "test response", response_text_type="dict"
    )

    # Make request
    response = test_client_with_mocks.post(
        "/qa",
        headers={"Authorization": "Bearer test-key"},
        json={"area": "test_area", "site": "test_site", "query": "test query"}
    )

    # Should succeed (graceful handling)
    assert response.status_code == 200
    data = response.json()

    # Should be converted to string
    assert isinstance(data["response_text"], str)
    assert "nested" in data["response_text"]  # String representation of dict

    # Should have logged an error
    mock_logger.error.assert_called_once()
    error_call = mock_logger.error.call_args[0][0]
    assert "not a string" in error_call
    assert "dict" in error_call


@patch("backend.endpoints.qa.get_image_registry")
@patch("backend.endpoints.qa.get_conversation_store")
@patch("backend.endpoints.qa.get_store_registry")
@patch("backend.endpoints.qa.get_storage_backend")
@patch("backend.endpoints.qa.genai.GenerativeModel")
@patch("backend.endpoints.qa.logger")
def test_type_validation_with_list_response(
    mock_logger, mock_model, mock_storage, mock_store_reg, mock_conv_store, mock_img_reg, test_client_with_mocks
):
    """Test validation when response_text is a list - should convert to string and log error."""
    # Setup mocks
    mock_store_reg.return_value.get_store_name.return_value = "test-store"
    mock_img_reg.return_value.get_images.return_value = []
    mock_conv_store.return_value.load_conversation.return_value = []

    # Mock Gemini API to return list instead of string
    mock_instance = MagicMock()
    mock_model.return_value = mock_instance
    mock_instance.generate_content.return_value = create_mock_gemini_response(
        "test response", response_text_type="list"
    )

    # Make request
    response = test_client_with_mocks.post(
        "/qa",
        headers={"Authorization": "Bearer test-key"},
        json={"area": "test_area", "site": "test_site", "query": "test query"}
    )

    # Should succeed (graceful handling)
    assert response.status_code == 200
    data = response.json()

    # Should be converted to string
    assert isinstance(data["response_text"], str)
    assert "test response" in data["response_text"]  # String representation of list

    # Should have logged an error
    mock_logger.error.assert_called_once()
    error_call = mock_logger.error.call_args[0][0]
    assert "not a string" in error_call
    assert "list" in error_call


@patch("backend.endpoints.qa.get_image_registry")
@patch("backend.endpoints.qa.get_conversation_store")
@patch("backend.endpoints.qa.get_store_registry")
@patch("backend.endpoints.qa.get_storage_backend")
@patch("backend.endpoints.qa.genai.GenerativeModel")
@patch("backend.endpoints.qa.logger")
def test_type_validation_with_int_response(
    mock_logger, mock_model, mock_storage, mock_store_reg, mock_conv_store, mock_img_reg, test_client_with_mocks
):
    """Test validation when response_text is an integer - should convert to string and log error."""
    # Setup mocks
    mock_store_reg.return_value.get_store_name.return_value = "test-store"
    mock_img_reg.return_value.get_images.return_value = []
    mock_conv_store.return_value.load_conversation.return_value = []

    # Mock Gemini API to return int instead of string
    mock_instance = MagicMock()
    mock_model.return_value = mock_instance
    mock_instance.generate_content.return_value = create_mock_gemini_response(
        None, response_text_type="int"
    )

    # Make request
    response = test_client_with_mocks.post(
        "/qa",
        headers={"Authorization": "Bearer test-key"},
        json={"area": "test_area", "site": "test_site", "query": "test query"}
    )

    # Should succeed (graceful handling)
    assert response.status_code == 200
    data = response.json()

    # Should be converted to string
    assert isinstance(data["response_text"], str)
    assert data["response_text"] == "12345"  # Integer converted to string

    # Should have logged an error
    mock_logger.error.assert_called_once()
    error_call = mock_logger.error.call_args[0][0]
    assert "not a string" in error_call
    assert "int" in error_call
