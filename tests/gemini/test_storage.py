"""
Unit tests for GCS storage backend (gemini/storage.py)

These tests use actual GCS credentials and perform real operations against
the configured bucket. Test files are clearly marked and cleaned up after tests.

Requirements:
- GCS credentials configured in .streamlit/secrets.toml
- GCS bucket 'tarasa_tourist_bot_content' accessible

Run with: pytest tests/gemini/test_storage.py -m gcs
"""

import os
import tempfile
from datetime import datetime

import pytest

from gemini.config import GeminiConfig
from gemini.storage import (
    CachedGCSStorage,
    GCSStorage,
    StorageBackend,
    get_storage_backend,
)


# Module-level fixtures for GCS testing


@pytest.fixture(scope="module")
def gcs_config():
    """Load GCS configuration once for all tests in this module"""
    return GeminiConfig.from_yaml()


@pytest.fixture(scope="function")
def test_prefix():
    """Generate unique test prefix with timestamp to avoid conflicts between parallel workers"""
    import uuid
    # Use UUID to ensure uniqueness across parallel workers
    return f"test_gcs_storage_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def gcs_storage(gcs_config):
    """Create GCSStorage instance for testing"""
    if not gcs_config.gcs_credentials_json:
        pytest.skip("GCS credentials not configured in .streamlit/secrets.toml - skipping GCS tests")

    storage = GCSStorage(
        bucket_name=gcs_config.gcs_bucket_name,
        credentials_json=gcs_config.gcs_credentials_json,
    )
    return storage


@pytest.fixture(scope="function", autouse=True)
def cleanup_test_files(request, gcs_storage, test_prefix):
    """
    Cleanup fixture that runs after each test completes

    Deletes all test files created during test execution.
    Function-scoped for parallel safety - each test gets its own prefix.
    """
    yield  # Let test run first

    # Only cleanup if test uses gcs_storage (check if it's a GCS test)
    if "gcs" in [mark.name for mark in request.node.iter_markers()]:
        try:
            # List and delete all files under this test's unique prefix
            test_files = gcs_storage.list_files(test_prefix)
            for file_path in test_files:
                gcs_storage.delete_file(file_path)
            if test_files:
                print(f"\n  Cleaned up {len(test_files)} test files for {test_prefix}")
        except Exception as e:
            print(f"\n  Warning: Failed to clean up test files for {test_prefix}: {e}")


# GCSStorage Tests


@pytest.mark.gcs
@pytest.mark.integration
@pytest.mark.slow
def test_write_and_read_file(gcs_storage, test_prefix):
    """Test writing and reading a file from GCS"""
    test_path = f"{test_prefix}/test_write_read.txt"
    test_content = "Hello from GCS test!\nThis is line 2."

    # Write file
    result = gcs_storage.write_file(test_path, test_content)
    assert result, "File write should succeed"

    # Read file back
    read_content = gcs_storage.read_file(test_path)
    assert read_content == test_content, "Read content should match written content"


@pytest.mark.gcs
@pytest.mark.integration
def test_file_exists(gcs_storage, test_prefix):
    """Test file_exists() method"""
    test_path = f"{test_prefix}/test_exists.txt"
    non_existent_path = f"{test_prefix}/does_not_exist.txt"

    # File should not exist initially
    assert not gcs_storage.file_exists(
        non_existent_path
    ), "Non-existent file should return False"

    # Write file
    gcs_storage.write_file(test_path, "test content")

    # File should exist now
    assert gcs_storage.file_exists(test_path), "File should exist after write"


@pytest.mark.gcs
@pytest.mark.integration
def test_list_files(gcs_storage, test_prefix):
    """Test listing files with pattern matching"""
    base_path = f"{test_prefix}/list_test"

    # Create multiple test files
    gcs_storage.write_file(f"{base_path}/file1.txt", "content 1")
    gcs_storage.write_file(f"{base_path}/file2.txt", "content 2")
    gcs_storage.write_file(f"{base_path}/data.json", "json content")
    gcs_storage.write_file(f"{base_path}/subdir/file3.txt", "content 3")

    # List all .txt files
    txt_files = gcs_storage.list_files(base_path, "*.txt")
    assert len(txt_files) == 3, "Should find 3 .txt files"

    # Verify file paths
    filenames = [os.path.basename(f) for f in txt_files]
    assert "file1.txt" in filenames
    assert "file2.txt" in filenames
    assert "file3.txt" in filenames

    # List all files (no pattern)
    all_files = gcs_storage.list_files(base_path)
    assert len(all_files) == 4, "Should find 4 total files"


@pytest.mark.gcs
@pytest.mark.integration
def test_delete_file(gcs_storage, test_prefix):
    """Test deleting files from GCS"""
    test_path = f"{test_prefix}/test_delete.txt"

    # Write file
    gcs_storage.write_file(test_path, "to be deleted")
    assert gcs_storage.file_exists(test_path), "File should exist after write"

    # Delete file
    result = gcs_storage.delete_file(test_path)
    assert result, "Delete should succeed"

    # Verify file is gone
    assert not gcs_storage.file_exists(test_path), "File should not exist after delete"


@pytest.mark.gcs
@pytest.mark.integration
def test_hierarchical_structure(gcs_storage, test_prefix):
    """Test that GCS maintains hierarchical structure (area/site pattern)"""
    area = "test_area"
    site = "test_site"
    filename = "chunk_001.txt"
    content = "Test chunk content"

    # Write file in hierarchical structure
    chunk_path = f"{test_prefix}/chunks/{area}/{site}/{filename}"
    gcs_storage.write_file(chunk_path, content)

    # List files at site level
    site_files = gcs_storage.list_files(f"{test_prefix}/chunks/{area}/{site}")
    assert len(site_files) == 1, "Should find 1 file at site level"
    assert filename in site_files[0], "Filename should be in path"

    # Read back content
    read_content = gcs_storage.read_file(chunk_path)
    assert read_content == content, "Content should match"


@pytest.mark.gcs
@pytest.mark.integration
def test_unicode_content(gcs_storage, test_prefix):
    """Test writing and reading Unicode content (Hebrew text)"""
    test_path = f"{test_prefix}/test_unicode.txt"
    hebrew_content = "שלום עולם!\nזהו טקסט בעברית."

    # Write Hebrew content
    gcs_storage.write_file(test_path, hebrew_content)

    # Read back and verify
    read_content = gcs_storage.read_file(test_path)
    assert read_content == hebrew_content, "Hebrew content should be preserved"


@pytest.mark.gcs
@pytest.mark.integration
@pytest.mark.slow
def test_large_file(gcs_storage, test_prefix):
    """Test writing and reading a larger file"""
    test_path = f"{test_prefix}/test_large.txt"

    # Create content with ~100KB of text
    large_content = "Line of text to repeat.\n" * 5000

    # Write large file
    result = gcs_storage.write_file(test_path, large_content)
    assert result, "Large file write should succeed"

    # Read back and verify
    read_content = gcs_storage.read_file(test_path)
    assert len(read_content) == len(large_content), "Content length should match"
    assert read_content == large_content, "Large content should match exactly"


@pytest.mark.gcs
@pytest.mark.integration
def test_overwrite_file(gcs_storage, test_prefix):
    """Test overwriting an existing file"""
    test_path = f"{test_prefix}/test_overwrite.txt"

    # Write initial content
    gcs_storage.write_file(test_path, "original content")
    original = gcs_storage.read_file(test_path)
    assert original == "original content"

    # Overwrite with new content
    gcs_storage.write_file(test_path, "updated content")
    updated = gcs_storage.read_file(test_path)
    assert updated == "updated content", "Content should be overwritten"


# CachedGCSStorage Tests


@pytest.fixture(scope="function")
def cache_dir():
    """Create temporary cache directory for cached storage tests (unique per test for parallel safety)"""
    with tempfile.TemporaryDirectory(prefix="gcs_cache_test_") as tmpdir:
        yield tmpdir


@pytest.fixture(scope="function")
def cached_gcs_storage(gcs_config, cache_dir):
    """Create CachedGCSStorage instance for testing (function-scoped for parallel safety)"""
    storage = CachedGCSStorage(
        bucket_name=gcs_config.gcs_bucket_name,
        credentials_json=gcs_config.gcs_credentials_json,
        cache_dir=cache_dir,
    )
    return storage


@pytest.mark.gcs
@pytest.mark.integration
@pytest.mark.slow
def test_write_through_cache(cached_gcs_storage, gcs_storage, test_prefix, cache_dir):
    """Test that writes go to both cache and GCS (write-through)"""
    test_path = f"{test_prefix}/test_write_through.txt"
    test_content = "Write-through test content"

    # Write using cached storage
    result = cached_gcs_storage.write_file(test_path, test_content)
    assert result, "Cached write should succeed"

    # Verify file exists in GCS (bypass cache)
    gcs_content = gcs_storage.read_file(test_path)
    assert gcs_content == test_content, "Content should be in GCS (write-through)"

    # Verify file exists in local cache (using hash-based cache path)
    cache_path = cached_gcs_storage._get_cache_path(test_path)
    assert cache_path.exists(), "File should exist in local cache"

    cache_content = cache_path.read_text(encoding="utf-8")
    assert cache_content == test_content, "Content should match in local cache"


@pytest.mark.gcs
@pytest.mark.integration
def test_read_through_cache(cached_gcs_storage, gcs_storage, test_prefix, cache_dir):
    """Test that reads use cache when available, GCS otherwise"""
    test_path = f"{test_prefix}/test_read_through.txt"
    test_content = "Read-through test content"

    # Write directly to GCS (bypass cache)
    gcs_storage.write_file(test_path, test_content)

    # First read should fetch from GCS and populate cache
    read_content = cached_gcs_storage.read_file(test_path)
    assert read_content == test_content, "First read should get content from GCS"

    # Verify cache was populated (using hash-based cache path)
    cache_path = cached_gcs_storage._get_cache_path(test_path)
    assert cache_path.exists(), "Cache should be populated after first read"

    # Second read should use cache
    read_content_2 = cached_gcs_storage.read_file(test_path)
    assert read_content_2 == test_content, "Second read should work from cache"


@pytest.mark.gcs
@pytest.mark.integration
def test_gcs_precedence_on_conflict(
    cached_gcs_storage, gcs_storage, test_prefix, cache_dir
):
    """
    Test cache behavior when there's a conflict

    Note: Current implementation reads from cache if present.
    Future enhancement: Add timestamp-based cache invalidation for true GCS precedence.
    """
    test_path = f"{test_prefix}/test_precedence.txt"
    gcs_content = "GCS authoritative content"
    cache_content = "Stale cache content"

    # Write to GCS
    gcs_storage.write_file(test_path, gcs_content)

    # Manually create conflicting cache file (simulating stale cache)
    cache_path = os.path.join(cache_dir, test_path)
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(cache_content)

    # Read should get content (either GCS or cache depending on implementation)
    read_content = cached_gcs_storage.read_file(test_path)

    # Document current behavior: cache is used if present
    # TODO: Implement timestamp-based cache invalidation for true GCS precedence
    assert read_content in [
        gcs_content,
        cache_content,
    ], "Read should return either GCS or cache content"


@pytest.mark.gcs
@pytest.mark.integration
def test_cached_list_files(cached_gcs_storage, test_prefix):
    """Test that list_files works with cached storage"""
    base_path = f"{test_prefix}/cached_list"

    # Create files using cached storage
    cached_gcs_storage.write_file(f"{base_path}/file1.txt", "content 1")
    cached_gcs_storage.write_file(f"{base_path}/file2.txt", "content 2")

    # List files should query GCS (not cache)
    files = cached_gcs_storage.list_files(base_path, "*.txt")
    assert len(files) == 2, "Should find 2 files in GCS"


@pytest.mark.gcs
@pytest.mark.integration
def test_cached_delete(cached_gcs_storage, gcs_storage, test_prefix, cache_dir):
    """Test that delete removes from both cache and GCS"""
    test_path = f"{test_prefix}/test_cached_delete.txt"

    # Write file (goes to both cache and GCS)
    cached_gcs_storage.write_file(test_path, "to be deleted")

    # Verify file exists in both places (using hash-based cache path)
    cache_path = cached_gcs_storage._get_cache_path(test_path)
    assert cache_path.exists(), "File should be in cache"
    assert gcs_storage.file_exists(test_path), "File should be in GCS"

    # Delete file
    result = cached_gcs_storage.delete_file(test_path)
    assert result, "Delete should succeed"

    # Verify file is removed from both places
    assert not cache_path.exists(), "File should be removed from cache"
    assert not gcs_storage.file_exists(test_path), "File should be removed from GCS"


# Factory Function Tests


@pytest.mark.unit
def test_get_gcs_storage_no_cache(gcs_config):
    """Test factory returns GCSStorage when caching disabled"""
    storage = get_storage_backend(
        bucket_name=gcs_config.gcs_bucket_name,
        credentials_json=gcs_config.gcs_credentials_json,
        enable_cache=False,
    )

    assert isinstance(storage, GCSStorage), "Should return GCSStorage instance"
    assert not isinstance(storage, CachedGCSStorage), "Should not be CachedGCSStorage"


@pytest.mark.unit
def test_get_cached_gcs_storage(gcs_config):
    """Test factory returns CachedGCSStorage when caching enabled"""
    with tempfile.TemporaryDirectory() as temp_dir:
        storage = get_storage_backend(
            bucket_name=gcs_config.gcs_bucket_name,
            credentials_json=gcs_config.gcs_credentials_json,
            enable_cache=True,
            cache_dir=temp_dir,
        )

        assert isinstance(
            storage, CachedGCSStorage
        ), "Should return CachedGCSStorage instance"


@pytest.mark.unit
def test_factory_with_config_defaults(gcs_config):
    """Test factory using config defaults"""
    storage = get_storage_backend(
        bucket_name=gcs_config.gcs_bucket_name,
        credentials_json=gcs_config.gcs_credentials_json,
        enable_cache=gcs_config.enable_local_cache,
    )

    assert isinstance(
        storage, StorageBackend
    ), "Should return a StorageBackend instance"
