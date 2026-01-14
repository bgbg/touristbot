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
