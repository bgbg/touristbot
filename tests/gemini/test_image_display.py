"""Tests for image display in Streamlit UI"""

import pytest


def test_gcs_path_to_url_conversion():
    """Test that GCS paths are correctly converted to public URLs (fallback mode)"""
    from gemini.main_qa import _get_image_display_url

    # Test full GCS URI (gs://bucket/path) without image_storage (public URL fallback)
    gcs_uri = "gs://tarasa_tourist_bot_content/images/area/site/doc/image_001.jpg"
    expected_url = "https://storage.googleapis.com/tarasa_tourist_bot_content/images/area/site/doc/image_001.jpg"
    assert _get_image_display_url(gcs_uri, "tarasa_tourist_bot_content", image_storage=None) == expected_url

    # Test relative path (images/area/site/doc/image_001.jpg) without image_storage
    relative_path = "images/area/site/doc/image_001.jpg"
    expected_url = "https://storage.googleapis.com/tarasa_tourist_bot_content/images/area/site/doc/image_001.jpg"
    assert _get_image_display_url(relative_path, "tarasa_tourist_bot_content", image_storage=None) == expected_url

    # Test with Hebrew characters in path
    hebrew_path = "images/hefer_valley/agamon_hefer/אגמון חפר/image_001.jpg"
    # URL encoding is handled by requests/browser
    expected_url = "https://storage.googleapis.com/tarasa_tourist_bot_content/images/hefer_valley/agamon_hefer/אגמון חפר/image_001.jpg"
    assert _get_image_display_url(hebrew_path, "tarasa_tourist_bot_content", image_storage=None) == expected_url


def test_image_registry_gcs_path_format():
    """Test that image registry stores GCS paths correctly"""
    from gemini.image_registry import ImageRegistry
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_path = f.name

    try:
        registry = ImageRegistry(temp_path)

        # Add an image with a GCS path
        image_key = registry.add_image(
            area="hefer_valley",
            site="agamon_hefer",
            doc="test_doc",
            image_index=1,
            caption="Test caption",
            context_before="Before",
            context_after="After",
            gcs_path="images/hefer_valley/agamon_hefer/test_doc/image_001.jpg",  # Relative path
            file_api_uri="https://example.com/files/test",
            file_api_name="files/test",
            image_format="jpg"
        )

        # Retrieve the image
        image = registry.get_image(image_key)

        # The gcs_path should be stored as-is (relative path format)
        assert image.gcs_path == "images/hefer_valley/agamon_hefer/test_doc/image_001.jpg"

        # It should NOT have gs:// prefix at this point
        assert not image.gcs_path.startswith("gs://")

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_image_relevance_detection():
    """Test that we can detect when images are relevant to display"""
    from gemini.main_qa import _should_display_images

    # Test cases where images SHOULD be displayed
    assert _should_display_images("Tell me about the pelicans at the wetland", ["שקנאי"]) == True
    assert _should_display_images("What do the birds look like?", []) == True
    assert _should_display_images("Show me pictures", []) == True
    assert _should_display_images("Can I see images of the area?", []) == True
    assert _should_display_images("The pelicans are beautiful birds", ["pelican"]) == True

    # Test cases where images should NOT be displayed
    assert _should_display_images("What are the opening hours?", []) == False
    assert _should_display_images("How do I get there?", []) == False
    assert _should_display_images("Tell me about the history", []) == False
    assert _should_display_images("What activities are available?", []) == False


def test_structured_output_schema():
    """Test that ImageAwareResponse Pydantic schema is properly defined"""
    from gemini.main_qa import ImageAwareResponse

    # Test schema can be instantiated with valid data
    response = ImageAwareResponse(
        response_text="שלום! איך אפשר לעזור?",
        should_include_images=False,
        image_relevance={}
    )
    assert response.response_text == "שלום! איך אפשר לעזור?"
    assert response.should_include_images == False
    assert response.image_relevance == {}

    # Test with images
    response_with_images = ImageAwareResponse(
        response_text="הנה תמונות יפות של שקנאים",
        should_include_images=True,
        image_relevance={
            "https://example.com/image1": 85,
            "https://example.com/image2": 92
        }
    )
    assert response_with_images.should_include_images == True
    assert response_with_images.image_relevance["https://example.com/image1"] == 85

    # Test schema can be converted to JSON schema
    schema = ImageAwareResponse.model_json_schema()
    assert "properties" in schema
    assert "response_text" in schema["properties"]
    assert "should_include_images" in schema["properties"]
    assert "image_relevance" in schema["properties"]


def test_greeting_detection_structured_output():
    """Test that structured output can indicate greeting without images"""
    import json
    from gemini.main_qa import ImageAwareResponse

    # Simulate structured output for a greeting
    greeting_response = {
        "response_text": "שלום! אני חיליק, המדריך שלך באזור. במה אוכל לעזור?",
        "should_include_images": False,
        "image_relevance": {}
    }

    # Verify it can be parsed
    parsed = ImageAwareResponse(**greeting_response)
    assert parsed.should_include_images == False
    assert len(parsed.image_relevance) == 0

    # Simulate JSON parsing flow
    json_str = json.dumps(greeting_response)
    parsed_from_json = json.loads(json_str)
    assert parsed_from_json["should_include_images"] == False


def test_image_relevance_scoring_structured_output():
    """Test that structured output includes relevance scores for images"""
    import json

    # Simulate structured output with relevance scores
    image_response = {
        "response_text": "שימו לב כמה יפים השקנאים האלה! הם חיים באזור הזה כל השנה.",
        "should_include_images": True,
        "image_relevance": {
            "https://generativelanguage.googleapis.com/v1beta/files/image1": 95,
            "https://generativelanguage.googleapis.com/v1beta/files/image2": 88,
            "https://generativelanguage.googleapis.com/v1beta/files/image3": 45  # Low score, should be filtered
        }
    }

    # Verify scoring logic
    threshold = 60
    relevant_uris = [uri for uri, score in image_response["image_relevance"].items() if score >= threshold]
    assert len(relevant_uris) == 2
    assert "https://generativelanguage.googleapis.com/v1beta/files/image1" in relevant_uris
    assert "https://generativelanguage.googleapis.com/v1beta/files/image2" in relevant_uris
    assert "https://generativelanguage.googleapis.com/v1beta/files/image3" not in relevant_uris


def test_structured_output_parsing_fallback():
    """Test that malformed structured output falls back gracefully"""
    import json

    # Test various malformed responses
    malformed_responses = [
        "Just plain text without JSON",
        '{"response_text": "Incomplete}',
        '{"wrong_field": "value"}',
        ''
    ]

    for malformed in malformed_responses:
        try:
            parsed = json.loads(malformed)
            # If it parses, check fallback behavior
            response_text = parsed.get("response_text", malformed)
            should_include_images = parsed.get("should_include_images", True)
            image_relevance = parsed.get("image_relevance", {})
            # Fallback should provide defaults
            assert isinstance(should_include_images, bool)
            assert isinstance(image_relevance, dict)
        except json.JSONDecodeError:
            # Expected for malformed JSON
            # Fallback should use raw text
            response_text = malformed
            should_include_images = True
            image_relevance = {}
            assert response_text == malformed
