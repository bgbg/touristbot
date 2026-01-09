#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Topic Generation CLI Tool

Regenerate topics for a specific area/site without re-uploading content.
Useful for:
- Iterating on topic extraction prompts
- Manual topic updates
- Fixing failed topic generation

Usage:
    python gemini/generate_topics.py --area "Old City" --site "Western Wall"
    python gemini/generate_topics.py --area "Museums" --site "National Museum"
"""

import argparse
import json
import os
import sys

# Add parent directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import google.genai as genai

from gemini.config import GeminiConfig
from gemini.storage import get_storage_backend
from gemini.topic_extractor import extract_topics_from_chunks


def main():
    parser = argparse.ArgumentParser(
        description="Regenerate topics for a location from existing chunks"
    )
    parser.add_argument("--area", required=True, help="Area name")
    parser.add_argument("--site", required=True, help="Site name")
    args = parser.parse_args()

    area = args.area
    site = args.site

    print(f"Topic Generation for {area}/{site}")
    print("=" * 60)

    # Load configuration
    try:
        config = GeminiConfig.from_yaml()
    except Exception as e:
        print(f"Error loading configuration: {e}")
        sys.exit(1)

    # Initialize Gemini client
    try:
        client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    except Exception as e:
        print(f"Error initializing Gemini client: {e}")
        print("Make sure GOOGLE_API_KEY environment variable is set")
        sys.exit(1)

    # Get storage backend
    storage_backend = get_storage_backend(config)

    # Load chunks from GCS or local filesystem
    print(f"\nLoading chunks from storage...")
    try:
        if storage_backend:
            # Load from GCS
            chunks_path = f"{config.chunks_dir}/{area}/{site}"
            chunk_files = storage_backend.list_files(chunks_path, "*.txt")

            if not chunk_files:
                print(f"Error: No chunks found at {chunks_path}")
                sys.exit(1)

            print(f"Found {len(chunk_files)} chunk files")

            # Read all chunks
            combined_chunks = []
            for chunk_file in chunk_files:
                chunk_content = storage_backend.read_file(chunk_file)
                combined_chunks.append(chunk_content)

            chunks_text = "\n\n".join(combined_chunks)
        else:
            # Load from local filesystem
            chunks_dir = os.path.join(config.chunks_dir, area, site)
            if not os.path.exists(chunks_dir):
                print(f"Error: Chunks directory not found: {chunks_dir}")
                sys.exit(1)

            chunk_files = [
                f for f in os.listdir(chunks_dir) if f.endswith(".txt")
            ]

            if not chunk_files:
                print(f"Error: No chunks found in {chunks_dir}")
                sys.exit(1)

            print(f"Found {len(chunk_files)} chunk files")

            # Read all chunks
            combined_chunks = []
            for chunk_file in chunk_files:
                chunk_path = os.path.join(chunks_dir, chunk_file)
                with open(chunk_path, "r", encoding="utf-8") as f:
                    combined_chunks.append(f.read())

            chunks_text = "\n\n".join(combined_chunks)

        print(f"Loaded {len(chunks_text)} characters of content")

    except Exception as e:
        print(f"Error loading chunks: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Extract topics
    print(f"\nExtracting topics using {config.model_name}...")
    try:
        topics = extract_topics_from_chunks(
            chunks=chunks_text,
            area=area,
            site=site,
            model=config.model_name,
            client=client,
        )

        print(f"\nGenerated {len(topics)} topics:")
        for i, topic in enumerate(topics, 1):
            print(f"  {i}. {topic}")

    except Exception as e:
        print(f"Error extracting topics: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Save topics to storage
    print(f"\nSaving topics to storage...")
    try:
        topics_json = json.dumps(topics, ensure_ascii=False, indent=2)

        if storage_backend:
            # Save to GCS
            topics_path = f"topics/{area}/{site}/topics.json"
            storage_backend.write_file(topics_path, topics_json)
            print(f"Topics saved to GCS: {topics_path}")
        else:
            # Save to local filesystem
            topics_dir = os.path.join("topics", area, site)
            os.makedirs(topics_dir, exist_ok=True)
            topics_file = os.path.join(topics_dir, "topics.json")
            with open(topics_file, "w", encoding="utf-8") as f:
                f.write(topics_json)
            print(f"Topics saved locally: {topics_file}")

        print("\nTopic generation complete!")

    except Exception as e:
        print(f"Error saving topics: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
