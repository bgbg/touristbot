#!/usr/bin/env python3
"""
Test script for registry rebuild_from_api() functionality
"""

import sys
import os

# Add parent directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

import google.genai as genai
from gemini.config import GeminiConfig
from gemini.store_registry import StoreRegistry


def test_rebuild():
    """Test rebuilding registry from Gemini Files API"""

    print("=" * 70)
    print("TESTING REGISTRY REBUILD FROM GEMINI FILES API")
    print("=" * 70)

    # Load config
    try:
        config = GeminiConfig.from_yaml()
        print("✓ Loaded config successfully\n")
    except Exception as e:
        print(f"✗ Failed to load config: {e}")
        return

    # Create client
    try:
        client = genai.Client(api_key=config.api_key)
        print("✓ Created Gemini client\n")
    except Exception as e:
        print(f"✗ Failed to create client: {e}")
        return

    # Create a test registry (will use temporary file)
    test_registry_file = "test_store_registry_rebuild.json"

    try:
        # Create registry instance
        registry = StoreRegistry(registry_file=test_registry_file)
        print(f"✓ Created test registry: {test_registry_file}\n")

        # Show existing registry before rebuild
        print("-" * 70)
        print("BEFORE REBUILD:")
        print("-" * 70)
        if registry.registry:
            print(f"Existing registry has {len(registry.registry)} entries:")
            for key, entry in registry.registry.items():
                print(f"  {key}: {entry.get('store_id')}")
        else:
            print("Registry is empty")
        print()

        # Perform rebuild
        print("-" * 70)
        print("PERFORMING REBUILD (merging with existing)...")
        print("-" * 70)

        try:
            stats = registry.rebuild_from_api(client, merge_with_existing=True)
            print("\n✓ Rebuild completed successfully!")
        except Exception as e:
            print(f"\n✗ Rebuild failed: {e}")
            import traceback

            traceback.print_exc()
            return

        # Show registry after rebuild
        print("\n" + "-" * 70)
        print("AFTER REBUILD:")
        print("-" * 70)
        if registry.registry:
            print(f"Registry now has {len(registry.registry)} entries:\n")
            for key, entry in sorted(registry.registry.items()):
                metadata = entry.get("metadata", {})
                area = metadata.get("area", "?")
                site = metadata.get("site", "?")
                file_count = metadata.get("file_count", 0)
                rebuilt = metadata.get("rebuilt_from_api", False)
                rebuilt_marker = " [REBUILT]" if rebuilt else ""

                print(f"  {area} / {site}:")
                print(f"    Store ID: {entry.get('store_id')}")
                print(f"    Files: {file_count}{rebuilt_marker}")
                if metadata.get("last_updated"):
                    print(f"    Updated: {metadata['last_updated']}")
                print()
        else:
            print("Registry is still empty")

        # Validation
        print("-" * 70)
        print("VALIDATION:")
        print("-" * 70)

        if stats["files_found"] == 0:
            print("⚠ No files found in Gemini API - cannot validate rebuild")
            print(
                "  Upload some content first using the Streamlit app to test rebuild"
            )
        elif stats["files_parsed"] == 0:
            print("⚠ No files with area/site encoding found")
            print(
                "  This is expected - existing files don't have encoding yet"
            )
            print(
                "  After uploading new content with encoding, rebuild will work"
            )
        else:
            print(f"✓ Successfully parsed {stats['files_parsed']} encoded files")
            print(f"✓ Created {stats['registry_entries']} registry entries")

            # Verify registry entries match parsed files
            if stats["registry_entries"] > 0:
                print(f"✓ Registry rebuilt successfully from API!")

        print()

    finally:
        # Clean up test file
        if os.path.exists(test_registry_file):
            os.remove(test_registry_file)
            print(f"✓ Cleaned up test file: {test_registry_file}")


if __name__ == "__main__":
    test_rebuild()
