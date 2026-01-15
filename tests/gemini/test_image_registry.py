"""Tests for image registry system with GCS backend"""

import pytest

from gemini.image_registry import ImageRegistry, ImageRecord
from tests.mock_storage import MockStorageBackend


@pytest.fixture
def mock_storage():
    """Create a mock storage backend for testing"""
    storage = MockStorageBackend()
    yield storage
    storage.clear()


def test_image_registry_initialization(mock_storage):
    """Test registry initialization with GCS backend"""
    registry = ImageRegistry(storage_backend=mock_storage, gcs_path="test/registry.json")
    assert registry.storage_backend == mock_storage
    assert registry.gcs_path == "test/registry.json"
    assert len(registry.registry) == 0


def test_image_registry_requires_storage_backend():
    """Test that ImageRegistry requires storage_backend parameter"""
    with pytest.raises(ValueError, match="ImageRegistry requires storage_backend"):
        ImageRegistry(storage_backend=None)


def test_add_image(mock_storage):
    """Test adding an image to registry"""
    registry = ImageRegistry(storage_backend=mock_storage, gcs_path="test/registry.json")

    image_key = registry.add_image(
        area="test_area",
        site="test_site",
        doc="test_doc",
        image_index=1,
        caption="Test caption",
        context_before="Before text",
        context_after="After text",
        gcs_path="images/test_area/test_site/test_doc/image_001.jpg",
        file_api_uri="https://example.com/files/test123",
        file_api_name="files/test123",
        image_format="jpg",
    )

    assert image_key == "test_area/test_site/test_doc/image_001"
    assert len(registry.registry) == 1

    # Verify the image was added
    image = registry.get_image(image_key)
    assert image is not None
    assert image.caption == "Test caption"
    assert image.area == "test_area"
    assert image.site == "test_site"
    assert image.doc == "test_doc"


def test_get_images_for_location(mock_storage):
    """Test querying images by location"""
    registry = ImageRegistry(storage_backend=mock_storage, gcs_path="test/registry.json")

    # Add multiple images
    registry.add_image(
        area="area1", site="site1", doc="doc1", image_index=1,
        caption="Image 1", context_before="", context_after="",
        gcs_path="images/area1/site1/doc1/image_001.jpg",
        file_api_uri="https://example.com/files/test1",
        file_api_name="files/test1", image_format="jpg"
    )

    registry.add_image(
        area="area1", site="site1", doc="doc1", image_index=2,
        caption="Image 2", context_before="", context_after="",
        gcs_path="images/area1/site1/doc1/image_002.jpg",
        file_api_uri="https://example.com/files/test2",
        file_api_name="files/test2", image_format="jpg"
    )

    registry.add_image(
        area="area1", site="site2", doc="doc2", image_index=1,
        caption="Image 3", context_before="", context_after="",
        gcs_path="images/area1/site2/doc2/image_001.jpg",
        file_api_uri="https://example.com/files/test3",
        file_api_name="files/test3", image_format="jpg"
    )

    # Query images for area1/site1
    images = registry.get_images_for_location("area1", "site1")
    assert len(images) == 2
    assert images[0].caption == "Image 1"
    assert images[1].caption == "Image 2"

    # Query images for area1/site2
    images = registry.get_images_for_location("area1", "site2")
    assert len(images) == 1
    assert images[0].caption == "Image 3"

    # Query images for specific doc
    images = registry.get_images_for_location("area1", "site1", "doc1")
    assert len(images) == 2


def test_search_by_caption(mock_storage):
    """Test searching images by caption"""
    registry = ImageRegistry(storage_backend=mock_storage, gcs_path="test/registry.json")

    registry.add_image(
        area="test_area", site="test_site", doc="test_doc", image_index=1,
        caption="A beautiful sunset",
        context_before="", context_after="",
        gcs_path="images/test_area/test_site/test_doc/image_001.jpg",
        file_api_uri="https://example.com/files/test1",
        file_api_name="files/test1", image_format="jpg"
    )

    registry.add_image(
        area="test_area", site="test_site", doc="test_doc", image_index=2,
        caption="Mountains at sunrise",
        context_before="", context_after="",
        gcs_path="images/test_area/test_site/test_doc/image_002.jpg",
        file_api_uri="https://example.com/files/test2",
        file_api_name="files/test2", image_format="jpg"
    )

    # Search for "sunset"
    results = registry.search_by_caption("sunset")
    assert len(results) == 1
    assert results[0].caption == "A beautiful sunset"

    # Search for "rise" (should match "sunrise")
    results = registry.search_by_caption("rise")
    assert len(results) == 1
    assert results[0].caption == "Mountains at sunrise"


def test_hebrew_text(mock_storage):
    """Test handling Hebrew text in captions"""
    registry = ImageRegistry(storage_backend=mock_storage, gcs_path="test/registry.json")

    hebrew_caption = "שקנאי – ציפור נודדת"
    image_key = registry.add_image(
        area="hefer_valley", site="agamon_hefer", doc="test", image_index=1,
        caption=hebrew_caption,
        context_before="טקסט לפני", context_after="טקסט אחרי",
        gcs_path="images/hefer_valley/agamon_hefer/test/image_001.jpg",
        file_api_uri="https://example.com/files/test1",
        file_api_name="files/test1", image_format="jpg"
    )

    # Verify Hebrew text is preserved
    image = registry.get_image(image_key)
    assert image.caption == hebrew_caption
    assert image.context_before == "טקסט לפני"
    assert image.context_after == "טקסט אחרי"

    # Search by Hebrew text
    results = registry.search_by_caption("שקנאי")
    assert len(results) == 1
    assert results[0].caption == hebrew_caption


def test_remove_image(mock_storage):
    """Test removing an image from registry"""
    registry = ImageRegistry(storage_backend=mock_storage, gcs_path="test/registry.json")

    image_key = registry.add_image(
        area="test_area", site="test_site", doc="test_doc", image_index=1,
        caption="Test", context_before="", context_after="",
        gcs_path="images/test_area/test_site/test_doc/image_001.jpg",
        file_api_uri="https://example.com/files/test1",
        file_api_name="files/test1", image_format="jpg"
    )

    assert len(registry.registry) == 1

    # Remove the image
    result = registry.remove_image(image_key)
    assert result is True
    assert len(registry.registry) == 0

    # Try to remove non-existent image
    result = registry.remove_image("nonexistent/key")
    assert result is False


def test_clear_location(mock_storage):
    """Test clearing all images for a location"""
    registry = ImageRegistry(storage_backend=mock_storage, gcs_path="test/registry.json")

    # Add images to multiple locations
    registry.add_image(
        area="area1", site="site1", doc="doc1", image_index=1,
        caption="Image 1", context_before="", context_after="",
        gcs_path="images/area1/site1/doc1/image_001.jpg",
        file_api_uri="https://example.com/files/test1",
        file_api_name="files/test1", image_format="jpg"
    )

    registry.add_image(
        area="area1", site="site1", doc="doc2", image_index=1,
        caption="Image 2", context_before="", context_after="",
        gcs_path="images/area1/site1/doc2/image_001.jpg",
        file_api_uri="https://example.com/files/test2",
        file_api_name="files/test2", image_format="jpg"
    )

    registry.add_image(
        area="area1", site="site2", doc="doc1", image_index=1,
        caption="Image 3", context_before="", context_after="",
        gcs_path="images/area1/site2/doc1/image_001.jpg",
        file_api_uri="https://example.com/files/test3",
        file_api_name="files/test3", image_format="jpg"
    )

    # Clear area1/site1
    count = registry.clear_location("area1", "site1")
    assert count == 2
    assert len(registry.registry) == 1

    # Verify only area1/site2 remains
    images = registry.get_images_for_location("area1", "site2")
    assert len(images) == 1


def test_get_stats(mock_storage):
    """Test getting registry statistics"""
    registry = ImageRegistry(storage_backend=mock_storage, gcs_path="test/registry.json")

    # Add images
    registry.add_image(
        area="area1", site="site1", doc="doc1", image_index=1,
        caption="Image 1", context_before="", context_after="",
        gcs_path="images/area1/site1/doc1/image_001.jpg",
        file_api_uri="https://example.com/files/test1",
        file_api_name="files/test1", image_format="jpg"
    )

    registry.add_image(
        area="area1", site="site2", doc="doc2", image_index=1,
        caption="Image 2", context_before="", context_after="",
        gcs_path="images/area1/site2/doc2/image_001.jpg",
        file_api_uri="https://example.com/files/test2",
        file_api_name="files/test2", image_format="jpg"
    )

    registry.add_image(
        area="area2", site="site3", doc="doc3", image_index=1,
        caption="Image 3", context_before="", context_after="",
        gcs_path="images/area2/site3/doc3/image_001.jpg",
        file_api_uri="https://example.com/files/test3",
        file_api_name="files/test3", image_format="jpg"
    )

    stats = registry.get_stats()
    assert stats["total_images"] == 3
    assert stats["unique_areas"] == 2
    assert stats["unique_sites"] == 3
    assert stats["unique_docs"] == 3
    assert len(stats["locations"]) == 3


def test_persistence(mock_storage):
    """Test that registry persists in GCS across instances"""
    # Create first registry and add image
    registry1 = ImageRegistry(storage_backend=mock_storage, gcs_path="test/registry.json")
    image_key = registry1.add_image(
        area="test_area", site="test_site", doc="test_doc", image_index=1,
        caption="Test", context_before="", context_after="",
        gcs_path="images/test_area/test_site/test_doc/image_001.jpg",
        file_api_uri="https://example.com/files/test1",
        file_api_name="files/test1", image_format="jpg"
    )

    # Create second registry instance - should load from mock GCS
    registry2 = ImageRegistry(storage_backend=mock_storage, gcs_path="test/registry.json")
    assert len(registry2.registry) == 1

    image = registry2.get_image(image_key)
    assert image is not None
    assert image.caption == "Test"


def test_in_memory_caching(mock_storage):
    """Test that registry uses in-memory caching"""
    registry = ImageRegistry(storage_backend=mock_storage, gcs_path="test/registry.json")

    # Add an image
    registry.add_image(
        area="test_area", site="test_site", doc="test_doc", image_index=1,
        caption="Test", context_before="", context_after="",
        gcs_path="images/test_area/test_site/test_doc/image_001.jpg",
        file_api_uri="https://example.com/files/test1",
        file_api_name="files/test1", image_format="jpg"
    )

    # Verify cache is loaded
    assert registry._cache_loaded is True

    # Multiple loads should use cache (not reload from storage)
    initial_load_count = len(mock_storage.files)
    registry._load()  # Should use cache, not reload
    assert len(mock_storage.files) == initial_load_count
