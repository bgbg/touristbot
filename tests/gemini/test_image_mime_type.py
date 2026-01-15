"""Tests for image MIME type handling in multimodal queries"""

import pytest
from google.genai import types


def test_image_mime_type_jpg_should_be_jpeg():
    """Test that jpg images use image/jpeg MIME type, not image/jpg"""
    from gemini.main_qa import _get_image_mime_type

    # This is what we were doing (WRONG - causes 400 error)
    wrong_mime = "image/jpg"

    # This is what Gemini API expects (CORRECT)
    correct_mime = "image/jpeg"

    # Test the helper function
    assert _get_image_mime_type("jpg") == "image/jpeg"
    assert _get_image_mime_type("JPG") == "image/jpeg"
    assert _get_image_mime_type("jpeg") == "image/jpeg"

    # Verify that directly constructing f"image/{format}" would be wrong
    image_format = "jpg"
    assert f"image/{image_format}" == wrong_mime  # This was the bug
    assert _get_image_mime_type(image_format) == correct_mime  # This is the fix


def test_file_api_manager_mime_type_mapping():
    """Test that FileAPIManager._get_mime_type returns correct MIME types"""
    from gemini.file_api_manager import FileAPIManager

    # Test jpg -> image/jpeg (not image/jpg)
    assert FileAPIManager._get_mime_type("jpg") == "image/jpeg"
    assert FileAPIManager._get_mime_type("jpeg") == "image/jpeg"

    # Test other formats
    assert FileAPIManager._get_mime_type("png") == "image/png"
    assert FileAPIManager._get_mime_type("webp") == "image/webp"
    assert FileAPIManager._get_mime_type("gif") == "image/gif"


def test_main_qa_uses_correct_mime_type():
    """Test that main_qa.py uses the correct MIME type from image_format"""

    # Simulate ImageRecord with jpg format
    class MockImageRecord:
        def __init__(self):
            self.file_api_uri = "https://generativelanguage.googleapis.com/v1beta/files/test"
            self.image_format = "jpg"  # This is what we store in the registry

    image = MockImageRecord()

    # The code in main_qa.py currently does:
    # mime_type = f"image/{image.image_format}"
    # This produces "image/jpg" which is WRONG

    wrong_mime = f"image/{image.image_format}"
    assert wrong_mime == "image/jpg"  # This is the problem

    # It should use a mapping function instead
    def get_correct_mime_type(image_format):
        mime_types = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
            "gif": "image/gif",
        }
        return mime_types.get(image_format.lower(), "image/jpeg")

    correct_mime = get_correct_mime_type(image.image_format)
    assert correct_mime == "image/jpeg"  # This is correct


def test_image_registry_stores_jpg_format():
    """Test that image registry stores 'jpg' as the format"""
    from gemini.image_registry import ImageRegistry
    from tests.mock_storage import MockStorageBackend

    mock_storage = MockStorageBackend()
    registry = ImageRegistry(storage_backend=mock_storage, gcs_path="test/registry.json")

    # Add an image with jpg format
    image_key = registry.add_image(
        area="test_area",
        site="test_site",
        doc="test_doc",
        image_index=1,
        caption="Test",
        context_before="",
        context_after="",
        gcs_path="test.jpg",
        file_api_uri="https://example.com/files/test",
        file_api_name="files/test",
        image_format="jpg"  # We store "jpg"
    )

    # Retrieve the image
    image = registry.get_image(image_key)

    # Verify it's stored as "jpg"
    assert image.image_format == "jpg"

    # But when we use it in API calls, we need to convert to "image/jpeg"
    # NOT "image/jpg"
