#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 1 Validation: Test if Gemini File Search extracts images from DOCX files

This script uploads a sample DOCX file with images to File Search and queries it
to determine if images are extracted and accessible in grounding_metadata.

Usage:
    python gemini/validate_file_search_images.py
"""

import json
import os
import sys
import time

# Add parent directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
os.chdir(parent_dir)

import google.genai as genai
from google.genai import types

from gemini.config import GeminiConfig
from gemini.file_search_store import FileSearchStoreManager
from gemini.store_registry import StoreRegistry


def main():
    print("=" * 70)
    print("Phase 1 Validation: File Search Image Support Test")
    print("=" * 70)
    print()

    # Load configuration
    print("Loading configuration...")
    try:
        config = GeminiConfig.from_yaml()
        print(f"✓ Config loaded")
        print(f"  File Search Store: {config.file_search_store_name}")
        print()
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        sys.exit(1)

    # Connect to Gemini
    print("Connecting to Gemini API...")
    try:
        client = genai.Client(api_key=config.api_key)
        print("✓ Connected to Gemini API")
        print()
    except Exception as e:
        print(f"❌ Error connecting to Gemini: {e}")
        sys.exit(1)

    # Initialize File Search Store Manager
    print("Initializing File Search Store...")
    try:
        fs_manager = FileSearchStoreManager(client)
        store_name = fs_manager.get_or_create_store(config.file_search_store_name)
        print(f"✓ Using store: {store_name}")
        print()
    except Exception as e:
        print(f"❌ Error initializing File Search Store: {e}")
        sys.exit(1)

    # Sample DOCX file path
    sample_docx = "data/locations/hefer_valley/agamon_hefer/אגמון חפר.docx"

    if not os.path.exists(sample_docx):
        print(f"❌ Sample DOCX file not found: {sample_docx}")
        sys.exit(1)

    print(f"Sample DOCX file: {sample_docx}")
    print(f"File size: {os.path.getsize(sample_docx) / 1024:.1f} KB")
    print()

    # Upload DOCX to File Search Store
    print("Uploading DOCX file to File Search Store...")
    print("(This may take a minute...)")

    # Copy file to avoid Hebrew filename encoding issues
    import shutil
    temp_docx = "temp_validation_test.docx"
    shutil.copy(sample_docx, temp_docx)
    print(f"  Copied to temporary file: {temp_docx}")

    try:
        operation = fs_manager.upload_to_file_search_store(
            file_search_store_name=store_name,
            file_path=temp_docx,
            area="hefer_valley",
            site="agamon_hefer",
            doc="validation_test",
            max_tokens_per_chunk=400,
            max_overlap_tokens=60,
        )
        print("✓ Upload complete")
        print()
    except Exception as e:
        print(f"❌ Error uploading file: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Clean up temp file
        if os.path.exists(temp_docx):
            os.remove(temp_docx)

    # Wait a moment for indexing
    print("Waiting for File Search indexing...")
    time.sleep(5)
    print()

    # Query the uploaded content
    test_queries = [
        "ספר לי על שקנאים",  # Tell me about pelicans (image caption in the doc)
        "מה יש באגמון חפר",  # What is in Agamon Hefer
        "צפרות נודדות",  # Migratory birds
    ]

    print("Querying uploaded DOCX with test queries...")
    print("=" * 70)
    print()

    metadata_filter = "area=hefer_valley AND site=agamon_hefer"

    for i, query in enumerate(test_queries, 1):
        print(f"Query {i}: {query}")
        print("-" * 70)

        try:
            response = client.models.generate_content(
                model=config.model_name,
                contents=query,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    tools=[
                        types.Tool(
                            file_search=types.FileSearch(
                                file_search_store_names=[store_name],
                                metadata_filter=metadata_filter,
                            )
                        )
                    ],
                ),
            )

            print(f"\nResponse Text:")
            print(response.text[:300] + "..." if len(response.text) > 300 else response.text)
            print()

            # Inspect grounding metadata
            if response.candidates:
                grounding_metadata = response.candidates[0].grounding_metadata

                if grounding_metadata and grounding_metadata.grounding_chunks:
                    print(f"✓ Found {len(grounding_metadata.grounding_chunks)} grounding chunks")

                    # Check for images in chunks
                    image_found = False
                    for j, chunk in enumerate(grounding_metadata.grounding_chunks[:3]):  # Check first 3
                        retrieved_context = chunk.retrieved_context

                        print(f"\n  Chunk {j+1}:")
                        print(f"    URI: {retrieved_context.uri}")
                        print(f"    Title: {retrieved_context.title}")

                        # Check if URI or content indicates an image
                        uri_lower = retrieved_context.uri.lower() if retrieved_context.uri else ""
                        if any(ext in uri_lower for ext in ['.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif']):
                            print(f"    🎯 IMAGE DETECTED in URI: {retrieved_context.uri}")
                            image_found = True

                        # Check text content preview
                        if retrieved_context.text:
                            preview = retrieved_context.text[:150]
                            print(f"    Text preview: {preview}...")

                        # Check metadata
                        if hasattr(retrieved_context, "metadata"):
                            print(f"    Metadata: {retrieved_context.metadata}")

                    if image_found:
                        print("\n  ✅ IMAGES FOUND IN GROUNDING METADATA!")
                    else:
                        print("\n  ℹ️  No images detected in grounding chunks")
                else:
                    print("  ⚠️  No grounding chunks found")
            else:
                print("  ⚠️  No candidates in response")

        except Exception as e:
            print(f"❌ Error querying: {e}")
            import traceback
            traceback.print_exc()

        print()
        print("=" * 70)
        print()

    # Summary
    print("\nVALIDATION SUMMARY")
    print("=" * 70)
    print("Please review the output above and check:")
    print()
    print("1. Do any URIs contain image file extensions (.jpg, .png, etc.)?")
    print("2. Are there separate chunks for images vs text?")
    print("3. Do grounding_chunks include image references?")
    print()
    print("Based on the results:")
    print("  - If images are found → Proceed with Phase 2A (Simple DOCX Upload)")
    print("  - If no images found → Proceed with Phase 2B (Hybrid Approach)")
    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
