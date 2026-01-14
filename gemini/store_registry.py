"""
Store Registry - Maps (area, site) pairs to Gemini File Search Store names
For tourism/museum app hierarchy
"""

import json
import os
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import google.genai as genai

from gemini.display_name_utils import parse_display_name


class StoreRegistry:
    """Manages mapping between (area, site) and Gemini store names"""

    def __init__(self, registry_file: str = "store_registry.json"):
        """
        Initialize store registry

        Args:
            registry_file: Path to JSON file storing the registry
        """
        self.registry_file = registry_file
        self.registry: Dict[str, Dict] = self._load_registry()
        # Global File Search Store name (shared across all locations)
        self._file_search_store_name: Optional[str] = self.registry.get(
            "_global", {}
        ).get("file_search_store_name")

    def _load_registry(self) -> Dict[str, Dict]:
        """Load registry from disk"""
        if os.path.exists(self.registry_file):
            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print(
                    f"Warning: Could not parse {self.registry_file}. Starting with empty registry."
                )
                return {}
        return {}

    def _save_registry(self):
        """Save registry to disk"""
        try:
            os.makedirs(os.path.dirname(self.registry_file) or ".", exist_ok=True)
            with open(self.registry_file, "w", encoding="utf-8") as f:
                json.dump(self.registry, f, indent=2, ensure_ascii=False)
            print(f"-> Registry saved to {self.registry_file}")
        except Exception as e:
            print(f"-> Warning: Could not save registry: {e}")

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
        print(f"-> Registered {area} - {site} ({file_count} files)")

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
            print("-> Registry is empty")
            return

        print("\n=== Store Registry (Tourism/Museum Sites) ===")
        if self._file_search_store_name:
            print(f"Global File Search Store: {self._file_search_store_name}")
            print("-" * 70)

        for key, entry in sorted(self.registry.items()):
            # Skip global entry
            if key == "_global":
                continue

            area, site = key.split(":", 1)
            metadata = entry.get("metadata", {}) if isinstance(entry, dict) else {}

            print(f"  {area.title()} - {site.title()}")
            if metadata.get("file_count"):
                print(f"    Files: {metadata['file_count']}")
            if metadata.get("document_count"):
                print(f"    Documents: {metadata['document_count']}")
            if metadata.get("last_updated"):
                print(f"    Last Updated: {metadata['last_updated']}")
        print("=" * 70)

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
        print("\n" + "=" * 70)
        print("REBUILDING REGISTRY FROM FILE SEARCH STORE")
        print("=" * 70)

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
            print(f"-> Preserving {len(old_registry)} existing registry entries")

        # Get File Search Store name from registry
        file_search_store_name = self.get_file_search_store_name()
        if not file_search_store_name:
            print("✗ Error: File Search Store not configured in registry")
            print("   Run upload first to create a File Search Store")
            if merge_with_existing:
                print("-> Keeping existing local registry")
                return stats
            else:
                raise ValueError("No File Search Store configured")

        # List all documents from File Search Store
        try:
            print(f"-> Querying File Search Store: {file_search_store_name}...")
            from gemini.file_search_store import FileSearchStoreManager
            file_search_manager = FileSearchStoreManager(client)
            documents = file_search_manager.list_documents_in_store(file_search_store_name)
            stats["files_found"] = len(documents)
            print(f"-> Found {len(documents)} document(s) in File Search Store")
        except Exception as e:
            print(f"✗ Error listing documents from File Search Store: {e}")
            raise

        if not documents:
            print("-> No documents found in File Search Store")
            if merge_with_existing:
                print("-> Keeping existing local registry")
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
            print(
                f"\n-> Skipped {len(skipped_files)} file(s) without area/site encoding:"
            )
            for name in skipped_files[:5]:  # Show first 5
                print(f"     - {name}")
            if len(skipped_files) > 5:
                print(f"     ... and {len(skipped_files) - 5} more")

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

            print(
                f"\n-> Merged {len(new_registry)} rebuilt entries with {len(old_registry)} existing"
            )
            print(f"-> Final registry has {len(self.registry)} entries")
        else:
            # Replace entirely with new registry
            self.registry = new_registry
            print(f"\n-> Replaced registry with {len(self.registry)} entries from API")

        # Save to disk
        self._save_registry()

        # Print summary
        print("\n" + "-" * 70)
        print("REBUILD SUMMARY:")
        print("-" * 70)
        print(f"  Documents in File Search Store: {stats['files_found']}")
        print(f"  Documents with metadata:        {stats['files_parsed']}")
        print(f"  Documents skipped (no metadata): {stats['files_skipped']}")
        print(f"  Registry entries created:       {stats['registry_entries']}")
        if merge_with_existing:
            print(f"  Existing entries preserved:     {stats['existing_preserved']}")
        print("-" * 70)

        return stats

    def clear_all(self) -> bool:
        """Clear entire registry (use with caution!)"""
        if not self.registry:
            print("-> Registry is already empty")
            return False

        print(
            f"\n⚠️  WARNING: About to clear {len(self.registry)} registry entry/entries!"
        )
        confirmation = input("Type 'CLEAR' to confirm: ")

        if confirmation != "CLEAR":
            print("-> Clear cancelled")
            return False

        self.registry = {}
        self._save_registry()
        print("-> Registry cleared")
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
        print(f"-> Set global File Search Store: {store_name}")

    def get_file_search_store_name(self) -> Optional[str]:
        """
        Get the global File Search Store name

        Returns:
            Store name if set, None otherwise
        """
        return self._file_search_store_name
