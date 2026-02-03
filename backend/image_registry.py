"""
Image Registry Module

Manages a JSON registry mapping images to their metadata, locations, and URIs.
Provides query methods to retrieve images by location (area/site/doc).

Registry is stored in GCS (Google Cloud Storage) as single source of truth.
"""

import json
import logging
import os
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

from backend.gcs_storage import StorageBackend

logger = logging.getLogger(__name__)


@dataclass
class ImageRecord:
    """Represents an image record in the registry"""

    image_key: str  # Format: "area/site/doc/image_XXX"
    area: str
    site: str
    doc: str
    image_index: int
    caption: str
    context_before: str
    context_after: str
    gcs_path: str
    file_api_uri: str
    file_api_name: str
    image_format: str

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ImageRecord":
        """Create ImageRecord from dictionary"""
        return cls(**data)


class ImageRegistry:
    """Manages image registry stored in GCS"""

    @staticmethod
    def _sanitize_path_component(value: str) -> str:
        """
        Sanitize path component to prevent path traversal attacks

        Args:
            value: Path component to sanitize

        Returns:
            Sanitized path component
        """
        # Remove path traversal sequences
        sanitized = value.replace('../', '').replace('..\\', '')
        # Replace path separators with underscores
        sanitized = sanitized.replace('/', '_').replace('\\', '_')
        # Remove any remaining dots at start
        sanitized = sanitized.lstrip('.')
        return sanitized

    def __init__(
        self,
        storage_backend: StorageBackend,
        gcs_path: str = "metadata/image_registry.json",
        local_path: str = "image_registry.json"
    ):
        """
        Initialize image registry with GCS storage backend

        Args:
            storage_backend: Storage backend for GCS operations (required)
            gcs_path: Path in GCS bucket for registry file
            local_path: Local file path for migration (legacy)

        Raises:
            ValueError: If storage_backend is not provided
        """
        if not storage_backend:
            raise ValueError(
                "ImageRegistry requires storage_backend parameter. "
                "GCS storage is mandatory for image registry."
            )

        self.storage_backend = storage_backend
        self.gcs_path = gcs_path
        self.local_path = local_path  # For migration only
        self.registry: Dict[str, ImageRecord] = {}
        self._cache_loaded = False  # Track if cache is populated

        # Perform automatic migration if needed, then load
        self._migrate_if_needed()
        self._load()

    def _migrate_if_needed(self):
        """
        Automatically migrate local registry file to GCS if needed

        This runs once on initialization. If local file exists but GCS doesn't,
        upload local to GCS and delete local file.
        """
        try:
            # Check if GCS file already exists
            gcs_exists = self.storage_backend.file_exists(self.gcs_path)
            local_exists = os.path.exists(self.local_path)

            if not gcs_exists and local_exists:
                logger.info(f"Migrating image registry from {self.local_path} to GCS {self.gcs_path}")

                # Read local file
                with open(self.local_path, "r", encoding="utf-8") as f:
                    local_data = f.read()

                # Upload to GCS
                success = self.storage_backend.write_file(self.gcs_path, local_data)

                if success:
                    logger.info("Migration successful, removing local file")
                    # Delete local file after successful upload
                    os.remove(self.local_path)
                    logger.info(f"Deleted local file: {self.local_path}")
                else:
                    logger.error("Migration failed: could not write to GCS")
            elif gcs_exists and local_exists:
                # Both exist - GCS takes precedence, warn about local file
                logger.warning(
                    f"Both GCS and local registry files exist. "
                    f"Using GCS as source of truth. "
                    f"Consider deleting local file: {self.local_path}"
                )
        except Exception as e:
            logger.error(f"Error during migration check: {e}")
            # Continue anyway - _load() will handle missing files

    def _load(self):
        """
        Load registry from GCS with in-memory caching

        Registry is cached in memory for the session lifetime.
        """
        if self._cache_loaded:
            # Already loaded, use cached version
            return

        try:
            # Read from GCS
            data_str = self.storage_backend.read_file(self.gcs_path)
            data = json.loads(data_str)

            # Convert dict to ImageRecord objects
            self.registry = {
                key: ImageRecord.from_dict(value) for key, value in data.items()
            }

            self._cache_loaded = True
            logger.debug(f"Loaded {len(self.registry)} images from GCS")

        except FileNotFoundError:
            # New installation or no images yet
            logger.info(f"No registry found in GCS at {self.gcs_path}, starting with empty registry")
            self.registry = {}
            self._cache_loaded = True
        except Exception as e:
            logger.error(f"Error loading image registry from GCS: {e}")
            raise IOError(f"Failed to load image registry from GCS: {e}")

    def _save(self):
        """
        Save the current in-memory registry to GCS

        GCS provides atomic write guarantees when writing the registry file.
        """
        try:
            # Convert ImageRecord objects to dicts
            data = {key: record.to_dict() for key, record in self.registry.items()}

            # Serialize to JSON
            data_str = json.dumps(data, ensure_ascii=False, indent=2)

            # Write to GCS
            success = self.storage_backend.write_file(self.gcs_path, data_str)

            if not success:
                raise IOError("Storage backend write_file returned False")

            logger.debug(f"Saved {len(self.registry)} images to GCS")

        except Exception as e:
            logger.error(f"Failed to save image registry to GCS: {e}")
            raise Exception(f"Failed to save image registry to GCS: {e}")

    def add_image(
        self,
        area: str,
        site: str,
        doc: str,
        image_index: int,
        caption: str,
        context_before: str,
        context_after: str,
        gcs_path: str,
        file_api_uri: str,
        file_api_name: str,
        image_format: str,
    ) -> str:
        """
        Add an image to the registry

        Args:
            area: Area identifier
            site: Site identifier
            doc: Document identifier
            image_index: Image index (1, 2, 3, ...)
            caption: Image caption
            context_before: Text before image
            context_after: Text after image
            gcs_path: GCS storage path
            file_api_uri: Gemini File API URI
            file_api_name: Gemini File API name
            image_format: Image format (jpg, png, etc.)

        Returns:
            Image key

        Raises:
            Exception: If save fails
        """
        # Sanitize path components to prevent path traversal
        area = self._sanitize_path_component(area)
        site = self._sanitize_path_component(site)
        doc = self._sanitize_path_component(doc)

        # Generate image key
        image_key = f"{area}/{site}/{doc}/image_{image_index:03d}"

        # Create record
        record = ImageRecord(
            image_key=image_key,
            area=area,
            site=site,
            doc=doc,
            image_index=image_index,
            caption=caption,
            context_before=context_before,
            context_after=context_after,
            gcs_path=gcs_path,
            file_api_uri=file_api_uri,
            file_api_name=file_api_name,
            image_format=image_format,
        )

        # Reload from disk before adding to avoid race condition
        self._load()

        # Add to registry
        self.registry[image_key] = record

        # Save
        self._save()

        return image_key

    def get_image(self, image_key: str) -> Optional[ImageRecord]:
        """
        Get image record by key

        Args:
            image_key: Image key (e.g., "area/site/doc/image_001")

        Returns:
            ImageRecord or None if not found
        """
        return self.registry.get(image_key)

    def get_images_for_location(
        self, area: str, site: str, doc: Optional[str] = None
    ) -> List[ImageRecord]:
        """
        Get all images for a location

        Args:
            area: Area identifier
            site: Site identifier
            doc: Optional document identifier (if None, returns all docs in site)

        Returns:
            List of ImageRecord objects
        """
        results = []

        for record in self.registry.values():
            if record.area == area and record.site == site:
                if doc is None or record.doc == doc:
                    results.append(record)

        # Sort by image index
        results.sort(key=lambda r: r.image_index)

        return results

    def search_by_caption(self, query: str) -> List[ImageRecord]:
        """
        Search images by caption text

        Args:
            query: Search query (case-insensitive substring match)

        Returns:
            List of ImageRecord objects matching query
        """
        query_lower = query.lower()
        results = []

        for record in self.registry.values():
            if query_lower in record.caption.lower():
                results.append(record)

        return results

    def remove_image(self, image_key: str) -> bool:
        """
        Remove an image from the registry

        Args:
            image_key: Image key

        Returns:
            True if removed, False if not found

        Raises:
            Exception: If save fails
        """
        if image_key in self.registry:
            del self.registry[image_key]
            self._save()
            return True

        return False

    def clear_location(self, area: str, site: str, doc: Optional[str] = None) -> int:
        """
        Remove all images for a location

        Args:
            area: Area identifier
            site: Site identifier
            doc: Optional document identifier

        Returns:
            Number of images removed

        Raises:
            Exception: If save fails
        """
        to_remove = []

        for key, record in self.registry.items():
            if record.area == area and record.site == site:
                if doc is None or record.doc == doc:
                    to_remove.append(key)

        for key in to_remove:
            del self.registry[key]

        if to_remove:
            self._save()

        return len(to_remove)

    def remove_images_for_location(self, area: str, site: str) -> int:
        """
        Alias for clear_location() - removes all images for an area/site

        Args:
            area: Area identifier
            site: Site identifier

        Returns:
            Number of images removed
        """
        return self.clear_location(area, site)

    def list_all_images(self) -> List[ImageRecord]:
        """
        List all images in registry

        Returns:
            List of all ImageRecord objects
        """
        return list(self.registry.values())

    def list_all_locations(self) -> List[tuple]:
        """
        List all unique locations with images

        Returns:
            List of (area, site, doc) tuples
        """
        locations = set()

        for record in self.registry.values():
            locations.add((record.area, record.site, record.doc))

        return sorted(locations)

    def get_stats(self) -> dict:
        """
        Get registry statistics

        Returns:
            Dictionary with stats: total_images, locations, areas, sites, docs
        """
        areas = set()
        sites = set()
        docs = set()

        for record in self.registry.values():
            areas.add(record.area)
            sites.add(f"{record.area}/{record.site}")
            docs.add(f"{record.area}/{record.site}/{record.doc}")

        return {
            "total_images": len(self.registry),
            "unique_areas": len(areas),
            "unique_sites": len(sites),
            "unique_docs": len(docs),
            "locations": self.list_all_locations(),
        }


def get_image_registry(
    storage_backend: StorageBackend,
    gcs_path: str = "metadata/image_registry.json"
) -> ImageRegistry:
    """
    Convenience function to get ImageRegistry instance

    Args:
        storage_backend: Storage backend for GCS operations (required)
        gcs_path: Path in GCS bucket for registry file

    Returns:
        ImageRegistry instance

    Raises:
        ValueError: If storage_backend is not provided
    """
    return ImageRegistry(storage_backend, gcs_path)
