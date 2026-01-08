#!/usr/bin/env python3
"""
Migration utility to upload local chunks to Google Cloud Storage

Usage:
    python scripts/migrate_to_gcs.py

This script:
1. Reads chunks from local data/chunks/ directory
2. Uploads them to GCS maintaining the same hierarchy
3. Reports statistics on uploaded files
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from gemini.config import GeminiConfig
from gemini.storage import get_storage_backend


def migrate_chunks():
    """Migrate local chunks to GCS"""
    print("=" * 60)
    print("Local Chunks to GCS Migration Utility")
    print("=" * 60)

    # Load configuration
    print("\n1. Loading configuration...")
    try:
        config = GeminiConfig.from_yaml()
        print(f"   ✓ Config loaded")
        print(f"   - Chunks directory: {config.chunks_dir}")
        print(f"   - GCS bucket: {config.gcs_bucket_name}")
    except Exception as e:
        print(f"   ✗ Failed to load config: {e}")
        return

    # Initialize GCS storage
    print("\n2. Connecting to GCS...")
    try:
        storage = get_storage_backend(
            bucket_name=config.gcs_bucket_name,
            credentials_json=config.gcs_credentials_json,
            enable_cache=False,  # No caching for migration
        )
        print(f"   ✓ Connected to GCS bucket: {config.gcs_bucket_name}")
    except Exception as e:
        print(f"   ✗ Failed to connect to GCS: {e}")
        print("   Make sure GCS credentials are configured in .streamlit/secrets.toml")
        return

    # Scan local chunks directory
    print(f"\n3. Scanning local chunks directory: {config.chunks_dir}")
    local_chunks_dir = Path(config.chunks_dir)

    if not local_chunks_dir.exists():
        print(f"   ✗ Directory not found: {config.chunks_dir}")
        return

    # Collect all chunk files
    chunk_files = []
    for root, dirs, files in os.walk(local_chunks_dir):
        for file in files:
            if file.endswith(".txt"):
                local_path = Path(root) / file
                # Calculate relative path from chunks_dir
                rel_path = local_path.relative_to(local_chunks_dir.parent)
                chunk_files.append((local_path, str(rel_path)))

    print(f"   ✓ Found {len(chunk_files)} chunk files")

    if len(chunk_files) == 0:
        print("   No chunks to migrate")
        return

    # Confirm migration
    print(f"\n4. Ready to upload {len(chunk_files)} files to GCS")
    response = input("   Proceed with migration? (yes/no): ")

    if response.lower() not in ["yes", "y"]:
        print("   Migration cancelled")
        return

    # Upload chunks to GCS
    print("\n5. Uploading chunks to GCS...")
    uploaded = 0
    failed = 0

    for local_path, gcs_path in chunk_files:
        try:
            # Read local file
            with open(local_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Upload to GCS
            success = storage.write_file(gcs_path, content)

            if success:
                uploaded += 1
                if uploaded % 10 == 0:
                    print(f"   ... uploaded {uploaded}/{len(chunk_files)}")
            else:
                failed += 1
                print(f"   ✗ Failed to upload: {gcs_path}")

        except Exception as e:
            failed += 1
            print(f"   ✗ Error uploading {gcs_path}: {e}")

    # Report results
    print("\n" + "=" * 60)
    print("Migration Complete")
    print("=" * 60)
    print(f"Total files: {len(chunk_files)}")
    print(f"Uploaded: {uploaded}")
    print(f"Failed: {failed}")

    if failed == 0:
        print("\n✓ All chunks successfully uploaded to GCS!")
    else:
        print(f"\n⚠ {failed} files failed to upload. Check errors above.")


if __name__ == "__main__":
    migrate_chunks()
