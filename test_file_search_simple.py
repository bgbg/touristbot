#!/usr/bin/env python3
"""Simple test of File Search with uploaded DOCX"""

import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import google.genai as genai
from google.genai import types
from gemini.config import GeminiConfig
from gemini.store_registry import StoreRegistry

# Load config
config = GeminiConfig.from_yaml()
client = genai.Client(api_key=config.api_key)

# Get store name from registry
registry = StoreRegistry(config.registry_path)
store_name = registry.get_file_search_store_name()

print(f"Using store: {store_name}")
print(f"Model: {config.model_name}")
print()

# Test query
query = "ספר לי על שקנאים"  # Tell me about pelicans
metadata_filter = 'area="hefer_valley" AND site="agamon_hefer"'

print(f"Query: {query}")
print(f"Filter: {metadata_filter}")
print()

# Generate content with File Search
response = client.models.generate_content(
    model=config.model_name,
    contents=[query],
    config=types.GenerateContentConfig(
        temperature=0.7,
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

print("Response:")
print(response.text)
print()

# Check grounding metadata
if response.candidates and response.candidates[0].grounding_metadata:
    gm = response.candidates[0].grounding_metadata
    if gm.grounding_chunks:
        print(f"\nFound {len(gm.grounding_chunks)} grounding chunks:")
        for i, chunk in enumerate(gm.grounding_chunks[:5], 1):
            rc = chunk.retrieved_context
            print(f"\n  Chunk {i}:")
            print(f"    URI: {rc.uri}")
            print(f"    Title: {rc.title}")
            if rc.text:
                print(f"    Text: {rc.text[:100]}...")

            # Check for images
            uri_lower = (rc.uri or "").lower()
            if any(ext in uri_lower for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                print(f"    ⭐ IMAGE DETECTED!")
else:
    print("No grounding metadata found")
