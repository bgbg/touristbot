"""
Image Registry Module

Manages a JSON registry mapping images to their metadata, locations, and URIs.
Provides query methods to retrieve images by location (area/site/doc).
"""

import json
import os
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional


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
    """Manages image registry (image_registry.json)"""

    def __init__(self, registry_path: str = "image_registry.json"):
        """
        Initialize image registry

        Args:
            registry_path: Path to registry JSON file
        """
        self.registry_path = registry_path
        self.registry: Dict[str, ImageRecord] = {}
        self._load()

    def _load(self):
        """Load registry from JSON file"""
        if os.path.exists(self.registry_path):
            try:
                with open(self.registry_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Convert dict to ImageRecord objects
                self.registry = {
                    key: ImageRecord.from_dict(value) for key, value in data.items()
                }

            except Exception as e:
                print(f"Warning: Could not load image registry: {e}")
                self.registry = {}
        else:
            self.registry = {}

    def _save(self):
        """Save registry to JSON file"""
        try:
            # Convert ImageRecord objects to dicts
            data = {key: record.to_dict() for key, record in self.registry.items()}

            with open(self.registry_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            raise Exception(f"Failed to save image registry: {e}")

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


def get_image_registry(registry_path: str = "image_registry.json") -> ImageRegistry:
    """
    Convenience function to get ImageRegistry instance

    Args:
        registry_path: Path to registry JSON file

    Returns:
        ImageRegistry instance
    """
    return ImageRegistry(registry_path)
