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
        self, area: str, site: str, store_name: str, metadata: Optional[Dict] = None
    ):
        """
        Register a store for an area/site pair

        Args:
            area: Area name (e.g., "Old City", "Museum District")
            site: Site name (e.g., "Western Wall", "National Museum")
            store_name: Gemini store name (e.g., "fileSearchStores/xxx")
            metadata: Optional additional metadata
        """
        key = self._make_key(area, site)

        # Check if this is an existing entry to preserve created_at
        existing_entry = self.registry.get(key)
        created_at = None
        if existing_entry and isinstance(existing_entry, dict):
            created_at = existing_entry.get("metadata", {}).get("created_at")

        entry = {
            "store_id": store_name,
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
        print(f"-> Registered store '{store_name}' for {area} - {site}")

    def get_store(self, area: str, site: str) -> Optional[str]:
        """
        Get store ID for an area/site pair

        Args:
            area: Area name
            site: Site name

        Returns:
            Store ID if found, None otherwise
        """
        key = self._make_key(area, site)
        entry = self.registry.get(key)

        if entry and isinstance(entry, dict):
            return entry.get("store_id")
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
            area, site = key.split(":", 1)
            store_id = entry.get("store_id") if isinstance(entry, dict) else entry
            result[(area, site)] = store_id
        return result

    def print_registry(self):
        """Print all registered stores in a formatted way"""
        if not self.registry:
            print("-> Registry is empty")
            return

        print("\n=== Store Registry (Tourism/Museum Sites) ===")
        for key, entry in sorted(self.registry.items()):
            area, site = key.split(":", 1)
            store_id = entry.get("store_id") if isinstance(entry, dict) else entry
            metadata = entry.get("metadata", {}) if isinstance(entry, dict) else {}

            print(f"  {area.title()} - {site.title()}")
            print(f"    Store ID: {store_id}")
            if metadata.get("last_updated"):
                print(f"    Last Updated: {metadata['last_updated']}")
        print("=" * 70)

    def rebuild_from_api(
        self, client: genai.Client, merge_with_existing: bool = True
    ) -> Dict[str, int]:
        """
        Rebuild registry from Gemini Files API by listing all files and parsing metadata

        This method queries client.files.list() to get all uploaded files, parses
        their display names to extract area/site information, and rebuilds the registry.

        Args:
            client: Gemini API client
            merge_with_existing: If True, merge with existing local registry (default)
                               If False, replace existing registry entirely

        Returns:
            Dictionary with rebuild statistics:
                - files_found: Total files in Gemini API
                - files_parsed: Files with valid area/site encoding
                - files_skipped: Files without encoding or expired
                - registry_entries: Number of (area, site) pairs created
                - existing_preserved: Entries from local registry kept (if merging)

        Raises:
            Exception: If API call fails
        """
        print("\n" + "=" * 70)
        print("REBUILDING REGISTRY FROM GEMINI FILES API")
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

        # List all files from Gemini API
        try:
            print("-> Querying Gemini Files API...")
            files = list(client.files.list())
            stats["files_found"] = len(files)
            print(f"-> Found {len(files)} file(s) in Gemini API")
        except Exception as e:
            print(f"✗ Error listing files from Gemini API: {e}")
            raise

        if not files:
            print("-> No files found in Gemini API")
            if merge_with_existing:
                print("-> Keeping existing local registry")
                return stats
            else:
                self.registry = {}
                self._save_registry()
                return stats

        # Group files by (area, site) pairs
        location_files: Dict[Tuple[str, str], List] = defaultdict(list)
        skipped_files = []

        for file in files:
            # Check if file is expired (optional, as API may filter these out)
            if hasattr(file, "expiration_time") and file.expiration_time:
                # File will expire - API handles deletion, but we could check here
                pass

            # Parse display name to extract area/site
            display_name = getattr(file, "display_name", None) or getattr(
                file, "name", "unknown"
            )

            parsed = parse_display_name(display_name)

            if parsed:
                area, site, filename = parsed
                location_files[(area, site)].append(file)
                stats["files_parsed"] += 1
            else:
                # File doesn't have encoded metadata (legacy file or non-encoded)
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

            # Get last_updated from newest file
            update_times = [
                f.update_time
                for f in files_list
                if hasattr(f, "update_time") and f.update_time
            ]
            last_updated = max(update_times).isoformat() if update_times else None

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
        print(f"  Files in Gemini API:         {stats['files_found']}")
        print(f"  Files with encoding:         {stats['files_parsed']}")
        print(f"  Files skipped (no encoding): {stats['files_skipped']}")
        print(f"  Registry entries created:    {stats['registry_entries']}")
        if merge_with_existing:
            print(f"  Existing entries preserved:  {stats['existing_preserved']}")
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
