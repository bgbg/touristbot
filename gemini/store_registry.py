"""
Store Registry - Maps (area, site) pairs to Gemini File Search Store names
For tourism/museum app hierarchy
"""

import json
import os
from datetime import datetime
from typing import Dict, Optional, Tuple


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
