"""
Store Registry - Maps (area, site) pairs to Gemini File Search Store names
For tourism/museum app hierarchy

Registry is stored in GCS (Google Cloud Storage) as single source of truth.
"""

import json
import logging
import os
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import google.genai as genai

from gemini.display_name_utils import parse_display_name
from gemini.storage import StorageBackend

logger = logging.getLogger(__name__)


class StoreRegistry:
    """Manages mapping between (area, site) and Gemini store names stored in GCS"""

    def __init__(
        self,
        storage_backend: StorageBackend,
        gcs_path: str = "metadata/store_registry.json",
        local_path: str = "gemini/store_registry.json"
    ):
        """
        Initialize store registry with GCS storage backend

        Args:
            storage_backend: Storage backend for GCS operations (required)
            gcs_path: Path in GCS bucket for registry file
            local_path: Local file path for migration (legacy)

        Raises:
            ValueError: If storage_backend is not provided
        """
        if not storage_backend:
            raise ValueError(
                "StoreRegistry requires storage_backend parameter. "
                "GCS storage is mandatory for store registry."
            )

        self.storage_backend = storage_backend
        self.gcs_path = gcs_path
        self.local_path = local_path  # For migration only
        self.registry: Dict[str, Dict] = {}
        self._cache_loaded = False  # Track if cache is populated

        # Perform automatic migration if needed, then load
        self._migrate_if_needed()
        self.registry = self._load_registry()

        # Global File Search Store name (shared across all locations)
        self._file_search_store_name: Optional[str] = self.registry.get(
            "_global", {}
        ).get("file_search_store_name")

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
                logger.info(f"Migrating store registry from {self.local_path} to GCS {self.gcs_path}")

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
            # Continue anyway - _load_registry() will handle missing files

    def _load_registry(self) -> Dict[str, Dict]:
        """
        Load registry from GCS with in-memory caching

        Registry is cached in memory for the session lifetime.
        """
        if self._cache_loaded:
            # Already loaded, use cached version
            return self.registry

        try:
            # Read from GCS
            data_str = self.storage_backend.read_file(self.gcs_path)
            registry = json.loads(data_str)

            self._cache_loaded = True
            logger.debug(f"Loaded {len(registry)} entries from GCS")
            return registry

        except FileNotFoundError:
            # New installation or no registry yet
            logger.info(f"No registry found in GCS at {self.gcs_path}, starting with empty registry")
            self._cache_loaded = True
            return {}
        except Exception as e:
            logger.error(f"Error loading store registry from GCS: {e}")
            raise IOError(f"Failed to load store registry from GCS: {e}")

    def _save_registry(self):
        """
        Save the current in-memory registry to GCS

        GCS provides atomic write guarantees when writing the registry file.
        """
        try:
            # Serialize to JSON
            data_str = json.dumps(self.registry, ensure_ascii=False, indent=2)

            # Write to GCS
            success = self.storage_backend.write_file(self.gcs_path, data_str)

            if not success:
                raise IOError("Storage backend write_file returned False")

            logger.debug(f"Saved {len(self.registry)} entries to GCS")

        except Exception as e:
            logger.error(f"Failed to save store registry to GCS: {e}")
            raise Exception(f"Failed to save store registry to GCS: {e}")

    @staticmethod
    def _make_key(area: str, site: str) -> str:
        """Create registry key from area and site"""
        return f"{area.lower().strip()}:{site.lower().strip()}"

    def register_store(
        self, area: str, site: str, metadata: Optional[Dict] = None
    ):
        """
        Register a location for File Search (all locations share same global store)

        Args:
            area: Area name (e.g., "hefer_valley")
            site: Site name (e.g., "agamon_hefer")
            metadata: Optional metadata (file_count, document_count, etc.)
        """
        key = self._make_key(area, site)

        # Check if this is an existing entry to preserve created_at
        existing_entry = self.registry.get(key)
        created_at = None
        if existing_entry and isinstance(existing_entry, dict):
            created_at = existing_entry.get("metadata", {}).get("created_at")

        entry = {
            "metadata": {
                "area": area,
                "site": site,
                "created_at": created_at or datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
            },
        }

        if metadata:
            entry["metadata"].update(metadata)

        self.registry[key] = entry
        self._save_registry()

        file_count = metadata.get("file_count", 0) if metadata else 0
        logger.info(f"Registered {area} - {site} ({file_count} files)")

    def get_store(self, area: str, site: str) -> Optional[str]:
        """
        Get File Search Store name for an area/site pair
        (Returns global store name since all locations share same store)

        Args:
            area: Area name
            site: Site name

        Returns:
            Global File Search Store name if location is registered, None otherwise
        """
        key = self._make_key(area, site)
        entry = self.registry.get(key)

        # If location is registered, return global store name
        if entry and isinstance(entry, dict):
            return self._file_search_store_name
        return None

    def get_entry(self, area: str, site: str) -> Optional[Dict]:
        """
        Get full registry entry for an area/site pair

        Args:
            area: Area name
            site: Site name

        Returns:
            Full entry dict if found, None otherwise
        """
        key = self._make_key(area, site)
        return self.registry.get(key)

    def list_all(self) -> Dict[Tuple[str, str], str]:
        """
        List all registered stores

        Returns:
            Dict mapping (area, site) tuples to store IDs
        """
        result = {}
        for key, entry in self.registry.items():
            # Skip global entry
            if key == "_global":
                continue
            area, site = key.split(":", 1)
            store_id = entry.get("store_id") if isinstance(entry, dict) else entry
            result[(area, site)] = store_id
        return result

    def print_registry(self):
        """Print all registered locations in a formatted way"""
        if not self.registry:
            logger.info("Registry is empty")
            return

        logger.info("Store Registry (Tourism/Museum Sites)")
        if self._file_search_store_name:
            logger.info(f"Global File Search Store: {self._file_search_store_name}")

        for key, entry in sorted(self.registry.items()):
            # Skip global entry
            if key == "_global":
                continue

            area, site = key.split(":", 1)
            metadata = entry.get("metadata", {}) if isinstance(entry, dict) else {}

            logger.info(f"{area.title()} - {site.title()}")
            if metadata.get("file_count"):
                logger.debug(f"  Files: {metadata['file_count']}")
            if metadata.get("document_count"):
                logger.debug(f"  Documents: {metadata['document_count']}")
            if metadata.get("last_updated"):
                logger.debug(f"  Last Updated: {metadata['last_updated']}")

    def rebuild_from_api(
        self, client: genai.Client, merge_with_existing: bool = True
    ) -> Dict[str, int]:
        """
        Rebuild registry from File Search Store by listing all documents and extracting metadata

        This method queries the File Search Store to get all uploaded documents, extracts
        their custom_metadata (area, site, doc) fields, and rebuilds the registry.

        Args:
            client: Gemini API client
            merge_with_existing: If True, merge with existing local registry (default)
                               If False, replace existing registry entirely

        Returns:
            Dictionary with rebuild statistics:
                - files_found: Total documents in File Search Store
                - files_parsed: Documents with valid area/site metadata
                - files_skipped: Documents without proper custom_metadata
                - registry_entries: Number of (area, site) pairs created
                - existing_preserved: Entries from local registry kept (if merging)

        Raises:
            Exception: If API call fails or File Search Store not configured
        """
        logger.info("REBUILDING REGISTRY FROM FILE SEARCH STORE")

        stats = {
            "files_found": 0,
            "files_parsed": 0,
            "files_skipped": 0,
            "registry_entries": 0,
            "existing_preserved": 0,
        }

        # Preserve existing registry if merging
        old_registry = dict(self.registry) if merge_with_existing else {}
        if merge_with_existing and old_registry:
            stats["existing_preserved"] = len(old_registry)
            logger.debug(f"Preserving {len(old_registry)} existing registry entries")

        # Get File Search Store name from registry
        file_search_store_name = self.get_file_search_store_name()
        if not file_search_store_name:
            logger.error("File Search Store not configured in registry")
            logger.info("Run upload first to create a File Search Store")
            if merge_with_existing:
                logger.info("Keeping existing local registry")
                return stats
            else:
                raise ValueError("No File Search Store configured")

        # List all documents from File Search Store
        try:
            logger.info(f"Querying File Search Store: {file_search_store_name}")
            from gemini.file_search_store import FileSearchStoreManager
            file_search_manager = FileSearchStoreManager(client)
            documents = file_search_manager.list_documents_in_store(file_search_store_name)
            stats["files_found"] = len(documents)
            logger.info(f"Found {len(documents)} document(s) in File Search Store")
        except Exception as e:
            logger.error(f"Error listing documents from File Search Store: {e}")
            raise

        if not documents:
            logger.info("No documents found in File Search Store")
            if merge_with_existing:
                logger.info("Keeping existing local registry")
                return stats
            else:
                self.registry = {}
                self._save_registry()
                return stats

        # Group documents by (area, site) pairs
        location_files: Dict[Tuple[str, str], List] = defaultdict(list)
        skipped_files = []

        for doc in documents:
            # Extract metadata from custom_metadata field
            metadata_dict = {}
            if hasattr(doc, "custom_metadata") and doc.custom_metadata:
                for meta_item in doc.custom_metadata:
                    if hasattr(meta_item, "key") and hasattr(meta_item, "string_value"):
                        metadata_dict[meta_item.key] = meta_item.string_value

            # Get area, site, and doc name from custom_metadata
            area = metadata_dict.get("area")
            site = metadata_dict.get("site")
            doc_name = metadata_dict.get("doc", "unknown")

            if area and site:
                location_files[(area, site)].append(doc)
                stats["files_parsed"] += 1
            else:
                # Document doesn't have proper custom_metadata
                display_name = getattr(doc, "display_name", None) or getattr(
                    doc, "name", "unknown"
                )
                skipped_files.append(display_name)
                stats["files_skipped"] += 1

        # Report skipped files
        if skipped_files:
            logger.warning(
                f"Skipped {len(skipped_files)} file(s) without area/site encoding"
            )
            for name in skipped_files[:5]:  # Show first 5
                logger.debug(f"Skipped file: {name}")
            if len(skipped_files) > 5:
                logger.debug(f"... and {len(skipped_files) - 5} more")

        # Build new registry from parsed files
        new_registry = {}

        for (area, site), files_list in location_files.items():
            key = self._make_key(area, site)

            # Use dummy store ID (we don't have actual store IDs with new API)
            # The store_id will be generated from area/site for consistency
            store_id = f"direct_upload_{area}_{site}_Tourism_RAG"

            # Get created_at from oldest file (first upload)
            created_times = [
                f.create_time
                for f in files_list
                if hasattr(f, "create_time") and f.create_time
            ]
            created_at = min(created_times).isoformat() if created_times else None

            # Get last_updated from newest file (using create_time since update_time doesn't exist)
            # Note: Gemini Files API doesn't provide update_time field, only create_time
            last_updated = max(created_times).isoformat() if created_times else None

            # Create registry entry
            new_registry[key] = {
                "store_id": store_id,
                "metadata": {
                    "area": area,
                    "site": site,
                    "created_at": created_at or datetime.now().isoformat(),
                    "last_updated": last_updated or datetime.now().isoformat(),
                    "file_count": len(files_list),
                    "rebuilt_from_api": True,
                },
            }

            stats["registry_entries"] += 1

        # Merge or replace
        if merge_with_existing:
            # Start with old registry, update with new data
            merged_registry = dict(old_registry)
            merged_registry.update(new_registry)
            self.registry = merged_registry

            logger.info(
                f"Merged {len(new_registry)} rebuilt entries with {len(old_registry)} existing"
            )
            logger.info(f"Final registry has {len(self.registry)} entries")
        else:
            # Replace entirely with new registry
            self.registry = new_registry
            logger.info(f"Replaced registry with {len(self.registry)} entries from API")

        # Save to disk
        self._save_registry()

        # Log summary
        logger.info("REBUILD SUMMARY:")
        logger.info(f"Documents in File Search Store: {stats['files_found']}")
        logger.info(f"Documents with metadata: {stats['files_parsed']}")
        logger.info(f"Documents skipped (no metadata): {stats['files_skipped']}")
        logger.info(f"Registry entries created: {stats['registry_entries']}")
        if merge_with_existing:
            logger.info(f"Existing entries preserved: {stats['existing_preserved']}")

        return stats

    def clear_all(self) -> bool:
        """Clear entire registry (use with caution!)"""
        if not self.registry:
            logger.info("Registry is already empty")
            return False

        logger.warning(
            f"WARNING: About to clear {len(self.registry)} registry entry/entries!"
        )
        confirmation = input("Type 'CLEAR' to confirm: ")

        if confirmation != "CLEAR":
            logger.info("Clear cancelled")
            return False

        self.registry = {}
        self._save_registry()
        logger.info("Registry cleared")
        return True

    def set_file_search_store_name(self, store_name: str):
        """
        Set the global File Search Store name (shared across all locations)

        Args:
            store_name: File Search Store resource name (e.g., "fileSearchStores/xxx")
        """
        if "_global" not in self.registry:
            self.registry["_global"] = {}

        self.registry["_global"]["file_search_store_name"] = store_name
        self._file_search_store_name = store_name
        self._save_registry()
        logger.info(f"Set global File Search Store: {store_name}")

    def get_file_search_store_name(self) -> Optional[str]:
        """
        Get the global File Search Store name

        Returns:
            Store name if set, None otherwise
        """
        return self._file_search_store_name
