"""
Storage backend abstraction for GCS with optional local caching

Provides GCS storage implementation as single source of truth,
with optional transparent local caching for performance.
"""

import hashlib
import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

from google.cloud import storage
from google.oauth2 import service_account


class StorageBackend(ABC):
    """Abstract base class for storage backends"""

    @abstractmethod
    def write_file(self, path: str, content: str) -> bool:
        """Write content to file at path. Returns True on success."""
        pass

    @abstractmethod
    def read_file(self, path: str) -> str:
        """Read and return content from file at path."""
        pass

    @abstractmethod
    def list_files(self, path: str, pattern: str = "*") -> List[str]:
        """List files in directory matching pattern. Returns list of paths."""
        pass

    @abstractmethod
    def delete_file(self, path: str) -> bool:
        """Delete file at path. Returns True on success."""
        pass

    @abstractmethod
    def file_exists(self, path: str) -> bool:
        """Check if file exists at path."""
        pass


class GCSStorage(StorageBackend):
    """Google Cloud Storage implementation"""

    def __init__(self, bucket_name: str, credentials_json: Optional[str] = None):
        """
        Initialize GCS storage backend

        Args:
            bucket_name: Name of the GCS bucket
            credentials_json: Service account JSON string (optional, uses default credentials if not provided)
        """
        self.bucket_name = bucket_name

        # Initialize GCS client
        if credentials_json:
            # Parse credentials from JSON string
            credentials_dict = json.loads(credentials_json)
            credentials = service_account.Credentials.from_service_account_info(
                credentials_dict
            )
            # Extract project_id from credentials
            project_id = credentials_dict.get("project_id")
            self.client = storage.Client(credentials=credentials, project=project_id)
        else:
            # Use default credentials (Application Default Credentials)
            self.client = storage.Client()

        self.bucket = self.client.bucket(bucket_name)

    def write_file(self, path: str, content: str) -> bool:
        """
        Write content to GCS blob

        Args:
            path: Blob path (e.g., 'chunks/area/site/file.txt')
            content: Text content to write

        Returns:
            True on success, False on failure
        """
        try:
            blob = self.bucket.blob(path)
            blob.upload_from_string(content, content_type="text/plain")
            return True
        except Exception as e:
            print(f"Error writing to GCS: {e}")
            return False

    def read_file(self, path: str) -> str:
        """
        Read content from GCS blob

        Args:
            path: Blob path

        Returns:
            File content as string

        Raises:
            FileNotFoundError: If blob doesn't exist
        """
        try:
            blob = self.bucket.blob(path)
            if not blob.exists():
                raise FileNotFoundError(f"File not found in GCS: {path}")
            return blob.download_as_text()
        except Exception as e:
            if isinstance(e, FileNotFoundError):
                raise
            raise IOError(f"Error reading from GCS: {e}")

    def list_files(self, path: str, pattern: str = "*") -> List[str]:
        """
        List files in GCS matching pattern

        Args:
            path: Directory path prefix (e.g., 'chunks/area/site/')
            pattern: File pattern to match (default: '*' matches all)

        Returns:
            List of blob paths matching the pattern
        """
        try:
            # Ensure path ends with / for directory listing
            if path and not path.endswith("/"):
                path = path + "/"

            # List all blobs with the prefix
            blobs = self.client.list_blobs(self.bucket_name, prefix=path)

            files = []
            for blob in blobs:
                # Skip directory markers (blobs ending with /)
                if blob.name.endswith("/"):
                    continue

                # Simple pattern matching (only supports * wildcard)
                if pattern == "*":
                    files.append(blob.name)
                elif pattern.startswith("*."):
                    # Match file extension
                    ext = pattern[1:]  # Remove *
                    if blob.name.endswith(ext):
                        files.append(blob.name)
                elif pattern in blob.name:
                    files.append(blob.name)

            return sorted(files)
        except Exception as e:
            print(f"Error listing files from GCS: {e}")
            return []

    def delete_file(self, path: str) -> bool:
        """
        Delete blob from GCS

        Args:
            path: Blob path

        Returns:
            True on success, False on failure
        """
        try:
            blob = self.bucket.blob(path)
            if blob.exists():
                blob.delete()
            return True
        except Exception as e:
            print(f"Error deleting from GCS: {e}")
            return False

    def file_exists(self, path: str) -> bool:
        """
        Check if blob exists in GCS

        Args:
            path: Blob path

        Returns:
            True if blob exists
        """
        try:
            blob = self.bucket.blob(path)
            return blob.exists()
        except Exception as e:
            print(f"Error checking file existence in GCS: {e}")
            return False


class CachedGCSStorage(StorageBackend):
    """
    GCS storage with transparent local caching

    - Writes go to both GCS and local cache (write-through)
    - Reads try local cache first, fall back to GCS (read-through)
    - GCS is always the source of truth
    """

    def __init__(
        self, bucket_name: str, credentials_json: Optional[str] = None, cache_dir: str = ".gcs_cache"
    ):
        """
        Initialize cached GCS storage

        Args:
            bucket_name: Name of the GCS bucket
            credentials_json: Service account JSON string
            cache_dir: Local directory for caching (default: .gcs_cache)
        """
        self.gcs = GCSStorage(bucket_name, credentials_json)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, path: str) -> Path:
        """Get local cache file path for GCS blob path"""
        # Use hash to avoid path length issues and special characters
        path_hash = hashlib.md5(path.encode()).hexdigest()
        return self.cache_dir / path_hash

    def _write_to_cache(self, path: str, content: str):
        """Write content to local cache"""
        try:
            cache_path = self._get_cache_path(path)
            cache_path.write_text(content, encoding="utf-8")
        except Exception as e:
            print(f"Warning: Failed to write to cache: {e}")

    def _read_from_cache(self, path: str) -> Optional[str]:
        """Read content from local cache if available"""
        try:
            cache_path = self._get_cache_path(path)
            if cache_path.exists():
                return cache_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"Warning: Failed to read from cache: {e}")
        return None

    def write_file(self, path: str, content: str) -> bool:
        """
        Write to GCS and local cache (write-through)

        Args:
            path: Blob path
            content: Text content

        Returns:
            True if write to GCS succeeds
        """
        # Write to GCS (source of truth)
        success = self.gcs.write_file(path, content)

        # Also write to cache if GCS write succeeded
        if success:
            self._write_to_cache(path, content)

        return success

    def read_file(self, path: str) -> str:
        """
        Read from cache first, fall back to GCS (read-through)

        Args:
            path: Blob path

        Returns:
            File content

        Raises:
            FileNotFoundError: If file doesn't exist in GCS
        """
        # Try cache first
        cached_content = self._read_from_cache(path)
        if cached_content is not None:
            return cached_content

        # Cache miss - read from GCS
        content = self.gcs.read_file(path)

        # Update cache
        self._write_to_cache(path, content)

        return content

    def list_files(self, path: str, pattern: str = "*") -> List[str]:
        """
        List files from GCS (cache doesn't affect listing)

        Args:
            path: Directory path prefix
            pattern: File pattern

        Returns:
            List of blob paths
        """
        return self.gcs.list_files(path, pattern)

    def delete_file(self, path: str) -> bool:
        """
        Delete from GCS and cache

        Args:
            path: Blob path

        Returns:
            True on success
        """
        # Delete from GCS
        success = self.gcs.delete_file(path)

        # Also delete from cache
        if success:
            try:
                cache_path = self._get_cache_path(path)
                if cache_path.exists():
                    cache_path.unlink()
            except Exception as e:
                print(f"Warning: Failed to delete from cache: {e}")

        return success

    def file_exists(self, path: str) -> bool:
        """
        Check if file exists in GCS (source of truth)

        Args:
            path: Blob path

        Returns:
            True if file exists in GCS
        """
        return self.gcs.file_exists(path)


def get_storage_backend(
    bucket_name: str,
    credentials_json: Optional[str] = None,
    enable_cache: bool = False,
    cache_dir: str = ".gcs_cache",
) -> StorageBackend:
    """
    Factory function to create appropriate storage backend

    Args:
        bucket_name: GCS bucket name
        credentials_json: Service account JSON string
        enable_cache: Whether to enable local caching
        cache_dir: Local cache directory

    Returns:
        GCSStorage or CachedGCSStorage instance
    """
    if enable_cache:
        return CachedGCSStorage(bucket_name, credentials_json, cache_dir)
    else:
        return GCSStorage(bucket_name, credentials_json)
