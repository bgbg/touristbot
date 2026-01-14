#!/usr/bin/env python3
"""List contents of File Search Store to see what was uploaded"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import google.genai as genai
from gemini.config import GeminiConfig
from gemini.store_registry import StoreRegistry
from gemini.file_search_store import FileSearchStoreManager

# Load config
config = GeminiConfig.from_yaml()
client = genai.Client(api_key=config.api_key)

# Get store
registry = StoreRegistry(config.registry_path)
store_name = registry.get_file_search_store_name()

print(f"Store: {store_name}")
print("=" * 70)
print()

# List documents
fs_manager = FileSearchStoreManager(client)

try:
    documents = fs_manager.list_documents_in_store(store_name)
    print(f"Found {len(documents)} documents in store")
    print()

    for i, doc in enumerate(documents, 1):
        print(f"\nDocument {i}:")
        print(f"  Name: {doc.name}")
        print(f"  Display Name: {getattr(doc, 'display_name', 'N/A')}")

        # Check for custom metadata
        if hasattr(doc, 'custom_metadata') and doc.custom_metadata:
            print(f"  Metadata:")
            for meta in doc.custom_metadata:
                print(f"    {meta.key}: {meta.string_value or meta.numeric_value}")

        # Check for media/content type
        if hasattr(doc, 'mime_type'):
            print(f"  MIME Type: {doc.mime_type}")

        # Look for any image-related attributes
        for attr in dir(doc):
            if 'image' in attr.lower() or 'media' in attr.lower():
                val = getattr(doc, attr, None)
                if val and not callable(val):
                    print(f"  {attr}: {val}")

except Exception as e:
    print(f"Error listing documents: {e}")
    import traceback
    traceback.print_exc()
