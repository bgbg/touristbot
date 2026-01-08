#!/usr/bin/env python3
"""
Integration test / exploration script for Gemini Files API
Research what metadata fields are available when listing files

Note: This is an exploration script with print-based output rather than
pytest assertions. It requires a valid API key and uploaded files to run.
"""

import pytest
import sys
import os

# Add parent directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

import google.genai as genai
from gemini.config import GeminiConfig

@pytest.mark.integration
def test_files_list():
    """Test client.files.list() and inspect available metadata fields"""

    # Load config
    try:
        config = GeminiConfig.from_yaml()
        print(f"✓ Loaded config successfully")
    except Exception as e:
        print(f"✗ Failed to load config: {e}")
        return

    # Create client
    try:
        client = genai.Client(api_key=config.api_key)
        print(f"✓ Created Gemini client")
    except Exception as e:
        print(f"✗ Failed to create client: {e}")
        return

    # List files
    print("\n" + "="*70)
    print("LISTING FILES FROM GEMINI API")
    print("="*70)

    try:
        files = list(client.files.list())
        print(f"\n✓ Found {len(files)} file(s) in Gemini API")

        if not files:
            print("\nℹ No files uploaded yet. Upload some content first to test metadata parsing.")
            return

        # Inspect first file in detail
        print("\n" + "-"*70)
        print("DETAILED METADATA FOR FIRST FILE:")
        print("-"*70)

        first_file = files[0]
        print(f"\nFile object type: {type(first_file)}")
        print(f"File object attributes: {dir(first_file)}")

        # Print all attributes and their values
        print("\nFile metadata fields:")
        for attr in dir(first_file):
            if not attr.startswith('_'):
                try:
                    value = getattr(first_file, attr)
                    if not callable(value):
                        print(f"  {attr}: {value}")
                except Exception as e:
                    print(f"  {attr}: <error reading: {e}>")

        # Print summary for all files
        print("\n" + "-"*70)
        print(f"SUMMARY OF ALL {len(files)} FILES:")
        print("-"*70)

        for i, file in enumerate(files, 1):
            print(f"\n[{i}] File:")
            try:
                print(f"  name: {file.name}")
            except AttributeError:
                print(f"  name: <not available>")

            try:
                print(f"  display_name: {file.display_name}")
            except AttributeError:
                print(f"  display_name: <not available>")

            try:
                print(f"  create_time: {file.create_time}")
            except AttributeError:
                print(f"  create_time: <not available>")

            try:
                print(f"  expiration_time: {file.expiration_time}")
            except AttributeError:
                print(f"  expiration_time: <not available>")

            try:
                print(f"  size_bytes: {file.size_bytes}")
            except AttributeError:
                print(f"  size_bytes: <not available>")

            try:
                print(f"  mime_type: {file.mime_type}")
            except AttributeError:
                print(f"  mime_type: <not available>")

    except Exception as e:
        print(f"✗ Error listing files: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_files_list()
